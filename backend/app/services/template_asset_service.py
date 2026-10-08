"""Template image asset upload and serving."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.models.email_template import EmailTemplate
from app.models.template_asset import TemplateAsset
from app.models.user import User
from app.schemas.templates import TemplateAssetResponse
from app.services.storage.factory import get_storage_provider, resolve_asset_key
from app.services.storage.local import LocalStorage

logger = get_logger(__name__)

ALLOWED_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}

EXT_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


class TemplateAssetService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.storage = LocalStorage()
        self.provider = get_storage_provider()

    async def upload(
        self,
        user: User,
        file: UploadFile,
        template_id: UUID | None = None,
    ) -> TemplateAssetResponse:
        if not file.filename:
            raise ValidationAppError("A file is required.")

        original = Path(file.filename).name
        suffix = Path(original).suffix.lower()
        if suffix not in EXT_TO_MIME:
            raise ValidationAppError(
                "Unsupported image type. Use JPEG, PNG, WEBP, or GIF."
            )

        content = await file.read()
        if not content:
            raise ValidationAppError("The uploaded file is empty.")
        max_bytes = self.settings.max_template_image_mb * 1024 * 1024
        if len(content) > max_bytes:
            raise ValidationAppError(
                f"Image exceeds the {self.settings.max_template_image_mb} MB limit."
            )

        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
                detected_format = (image.format or "").upper()
        except UnidentifiedImageError as exc:
            raise ValidationAppError("The uploaded file is not a valid image.") from exc
        except OSError as exc:
            raise ValidationAppError("The uploaded file is not a valid image.") from exc

        format_to_mime = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
            "GIF": "image/gif",
        }
        mime = format_to_mime.get(detected_format)
        if mime not in ALLOWED_MIME:
            raise ValidationAppError(
                "Unsupported image type. Use JPEG, PNG, WEBP, or GIF."
            )

        if template_id:
            owned = self.db.scalar(
                select(EmailTemplate).where(
                    EmailTemplate.id == template_id,
                    EmailTemplate.user_id == user.id,
                )
            )
            if owned is None:
                raise NotFoundError("Template not found")

        ext = ALLOWED_MIME[mime]
        storage_key = self.provider.save_template_image(content, ext) if hasattr(self.provider, "save_template_image") else None
        if storage_key is None:
            from uuid import uuid4 as _uuid4

            storage_key = f"template-images/{_uuid4()}.{ext}"
            self.provider.save(storage_key, content, content_type=mime)
        stored = Path(storage_key).name
        public_url = self.provider.get_url(storage_key)
        asset_id = uuid4()
        content_id = f"asset-{asset_id}@mailflow.local"

        asset = TemplateAsset(
            id=asset_id,
            user_id=user.id,
            template_id=template_id,
            original_filename=original,
            stored_filename=stored,
            storage_provider=self.provider.name,
            storage_key=storage_key,
            public_url=public_url,
            mime_type=mime,
            file_size=len(content),
            width=width,
            height=height,
            content_id=content_id,
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        logger.info(
            "template_asset.uploaded",
            user_id=str(user.id),
            asset_id=str(asset.id),
            mime=mime,
        )
        return self._to_response(asset)

    def get_owned(self, user: User, asset_id: UUID) -> TemplateAsset:
        asset = self.db.scalar(
            select(TemplateAsset).where(
                TemplateAsset.id == asset_id,
                TemplateAsset.user_id == user.id,
            )
        )
        if asset is None:
            raise NotFoundError("Template asset not found")
        return asset

    def read_content(self, user: User, asset_id: UUID) -> tuple[TemplateAsset, bytes]:
        asset = self.get_owned(user, asset_id)
        key = resolve_asset_key(
            storage_key=asset.storage_key,
            stored_filename=asset.stored_filename,
            kind="template-images",
        )
        try:
            content = self.provider.read(key)
        except Exception:
            path = self.storage.template_image_path(asset.stored_filename)
            if not path.exists():
                raise NotFoundError("Template asset file not found")
            content = path.read_bytes()
        return asset, content

    def _to_response(self, asset: TemplateAsset) -> TemplateAssetResponse:
        return TemplateAssetResponse(
            id=asset.id,
            template_id=asset.template_id,
            original_filename=asset.original_filename,
            mime_type=asset.mime_type,
            file_size=asset.file_size,
            width=asset.width,
            height=asset.height,
            content_id=asset.content_id,
            preview_url=f"/api/v1/template-assets/{asset.id}/content",
            cid_placeholder=f"cid:{asset.content_id}" if asset.content_id else None,
            created_at=asset.created_at,
        )
