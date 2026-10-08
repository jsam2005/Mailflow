"""Vercel Blob StorageProvider (production object storage)."""

from __future__ import annotations

from uuid import uuid4

import httpx

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.services.storage.base import StorageProvider

BLOB_API = "https://blob.vercel-storage.com"


class VercelBlobStorageProvider(StorageProvider):
    name = "vercel_blob"

    def __init__(self, token: str | None = None) -> None:
        settings = get_settings()
        self.token = token or settings.blob_read_write_token
        if not self.token:
            raise ValidationAppError("BLOB_READ_WRITE_TOKEN is not configured.")

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def save(self, key: str, content: bytes, *, content_type: str | None = None) -> str:
        cleaned = key.lstrip("/")
        headers = {
            **self._headers(),
            "x-api-version": "7",
            "x-vercel-blob-pathname": cleaned,
        }
        if content_type:
            headers["Content-Type"] = content_type
        with httpx.Client(timeout=60.0) as client:
            response = client.put(f"{BLOB_API}/{cleaned}", content=content, headers=headers)
        if response.status_code >= 400:
            raise ValidationAppError("Failed to store file in object storage.")
        data = response.json()
        return data.get("pathname") or cleaned

    def read(self, key: str) -> bytes:
        url = self.get_url(key)
        if not url:
            raise NotFoundError("Storage object not found.")
        with httpx.Client(timeout=60.0) as client:
            response = client.get(url)
        if response.status_code == 404:
            raise NotFoundError("Storage object not found.")
        if response.status_code >= 400:
            raise ValidationAppError("Failed to read file from object storage.")
        return response.content

    def delete(self, key: str) -> None:
        url = self.get_url(key)
        if not url:
            return
        with httpx.Client(timeout=30.0) as client:
            client.post(
                f"{BLOB_API}/delete",
                headers={**self._headers(), "x-api-version": "7"},
                json={"url": url},
            )

    def exists(self, key: str) -> bool:
        try:
            self.read(key)
            return True
        except NotFoundError:
            return False

    def get_url(self, key: str) -> str | None:
        # Store absolute URLs as keys when saved; otherwise construct pathname URL lookup
        # via list is not available — callers should persist public_url when uploading.
        if key.startswith("http://") or key.startswith("https://"):
            return key
        # Best-effort public URL pattern; prefer persisted public_url on TemplateAsset.
        return None

    def save_import_file(self, content: bytes, extension: str) -> str:
        key = f"imports/{uuid4()}.{extension.lower().lstrip('.')}"
        return self.save(key, content)

    def save_template_image(self, content: bytes, extension: str) -> str:
        key = f"template-images/{uuid4()}.{extension.lower().lstrip('.')}"
        return self.save(key, content, content_type=None)
