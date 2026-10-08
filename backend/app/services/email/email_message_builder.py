"""Build RFC 2822 MIME messages with plain/HTML parts and CID images."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from pathlib import Path
from typing import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.models.template_asset import TemplateAsset
from app.models.user import User
from app.services.storage.factory import get_storage_provider, resolve_asset_key
from app.services.storage.local import LocalStorage

ASSET_ID_ATTR = re.compile(
    r'data-mailflow-asset-id=(["\'])([0-9a-fA-F-]{36})\1',
    re.IGNORECASE,
)
IMG_TAG_WITH_ASSET = re.compile(
    r'<img\b[^>]*\bdata-mailflow-asset-id=(["\'])([0-9a-fA-F-]{36})\1[^>]*>',
    re.IGNORECASE,
)
SRC_ATTR = re.compile(r'\bsrc=(["\'])(.*?)\1', re.IGNORECASE)

ALLOWED_MIME = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}


@dataclass
class InlineImage:
    content_id: str
    filename: str
    mime_type: str
    content: bytes


@dataclass
class BuiltEmail:
    from_email: str
    from_name: str | None
    to_email: str
    subject: str
    html_body: str
    text_body: str
    inline_images: list[InlineImage] = field(default_factory=list)
    message_id: str | None = None

    def to_mime_bytes(self) -> bytes:
        msg = EmailMessage()
        if self.from_name:
            msg["From"] = formataddr((self.from_name, self.from_email))
        else:
            msg["From"] = self.from_email
        msg["To"] = self.to_email
        msg["Subject"] = self.subject
        msg["Message-ID"] = self.message_id or make_msgid(domain="mailflow.local")

        msg.set_content(self.text_body or " ")
        msg.add_alternative(self.html_body or "<p></p>", subtype="html")

        html_part = msg.get_body(preferencelist=("html",))
        if html_part is not None:
            for image in self.inline_images:
                maintype, _, subtype = image.mime_type.partition("/")
                html_part.add_related(
                    image.content,
                    maintype=maintype or "image",
                    subtype=subtype or "png",
                    cid=f"<{image.content_id}>",
                    filename=image.filename,
                )

        return msg.as_bytes()


class EmailMessageBuilder:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage = LocalStorage()
        self.provider = get_storage_provider()

    def build(
        self,
        *,
        user: User,
        from_email: str,
        from_name: str | None,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str | None = None,
    ) -> BuiltEmail:
        html_with_cid, images = self.transform_cid_images(user, html_body)
        return BuiltEmail(
            from_email=from_email,
            from_name=from_name,
            to_email=to_email,
            subject=subject,
            html_body=html_with_cid,
            text_body=text_body or _html_fallback_text(html_with_cid),
            inline_images=images,
            message_id=make_msgid(domain="mailflow.local"),
        )

    def transform_cid_images(
        self,
        user: User,
        html: str,
    ) -> tuple[str, list[InlineImage]]:
        """Replace asset URLs with cid: references and collect inline parts."""
        asset_ids = self._extract_asset_ids(html)
        if not asset_ids:
            return html, []

        assets = self._load_assets(user, asset_ids)
        images: list[InlineImage] = []
        id_to_cid: dict[str, str] = {}

        for asset_id, asset in assets.items():
            content = self._read_asset_bytes(asset)
            content_id = asset.content_id or f"asset-{asset.id}@mailflow.local"
            id_to_cid[str(asset.id)] = content_id
            images.append(
                InlineImage(
                    content_id=content_id,
                    filename=asset.original_filename,
                    mime_type=asset.mime_type,
                    content=content,
                )
            )

        def replace_img(match: re.Match[str]) -> str:
            tag = match.group(0)
            asset_id = match.group(2).lower()
            # Normalize UUID casing for lookup
            for key, cid in id_to_cid.items():
                if key.lower() == asset_id:
                    if SRC_ATTR.search(tag):
                        return SRC_ATTR.sub(f'src="cid:{cid}"', tag, count=1)
                    return tag.replace("<img", f'<img src="cid:{cid}"', 1)
            raise NotFoundError("A template image asset is missing or inaccessible.")

        transformed = IMG_TAG_WITH_ASSET.sub(replace_img, html)
        return transformed, images

    def _extract_asset_ids(self, html: str) -> list[UUID]:
        found: list[UUID] = []
        seen: set[str] = set()
        for match in ASSET_ID_ATTR.finditer(html or ""):
            raw = match.group(2)
            key = raw.lower()
            if key in seen:
                continue
            seen.add(key)
            try:
                found.append(UUID(raw))
            except ValueError as exc:
                raise ValidationAppError("Invalid template asset reference.") from exc
        return found

    def _load_assets(self, user: User, asset_ids: Iterable[UUID]) -> dict[str, TemplateAsset]:
        ids = list(asset_ids)
        stmt = select(TemplateAsset).where(
            TemplateAsset.user_id == user.id,
            TemplateAsset.id.in_(ids),
        )
        rows = list(self.db.scalars(stmt).all())
        by_id = {str(a.id): a for a in rows}
        for asset_id in ids:
            if str(asset_id) not in by_id:
                raise NotFoundError("A template image asset is missing or inaccessible.")
        return by_id

    def _read_asset_bytes(self, asset: TemplateAsset) -> bytes:
        if asset.mime_type not in ALLOWED_MIME:
            raise ValidationAppError("Unsupported image type in template.")
        max_bytes = self.settings.max_template_image_mb * 1024 * 1024
        if asset.file_size > max_bytes:
            raise ValidationAppError("Template image exceeds the configured size limit.")
        key = resolve_asset_key(
            storage_key=getattr(asset, "storage_key", None),
            stored_filename=asset.stored_filename,
            kind="template-images",
        )
        # Prefer configured provider; fall back to local path for legacy files.
        try:
            content = self.provider.read(key)
        except Exception:
            path: Path = self.storage.template_image_path(asset.stored_filename)
            if not path.exists():
                raise NotFoundError("A template image file is missing from storage.")
            content = path.read_bytes()
        if len(content) > max_bytes:
            raise ValidationAppError("Template image exceeds the configured size limit.")
        return content


def _html_fallback_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text or " "
