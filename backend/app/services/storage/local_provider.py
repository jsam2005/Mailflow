"""Local filesystem StorageProvider."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.services.storage.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    name = "local"

    def __init__(self, root: Path | None = None) -> None:
        settings = get_settings()
        self.root = (root or settings.storage_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, key: str, content: bytes, *, content_type: str | None = None) -> str:
        path = self._safe_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return key

    def read(self, key: str) -> bytes:
        path = self._safe_path(key)
        if not path.exists():
            raise NotFoundError("Storage object not found.")
        return path.read_bytes()

    def delete(self, key: str) -> None:
        path = self._safe_path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._safe_path(key).exists()

    def get_url(self, key: str) -> str | None:
        return None

    def save_import_file(self, content: bytes, extension: str) -> str:
        safe_ext = extension.lower().lstrip(".")
        key = f"imports/{uuid4()}.{safe_ext}"
        self.save(key, content)
        return key

    def save_template_image(self, content: bytes, extension: str) -> str:
        safe_ext = extension.lower().lstrip(".")
        key = f"template-images/{uuid4()}.{safe_ext}"
        self.save(key, content)
        return key

    def validation_cache_key(self, session_id: str) -> str:
        return f"imports/{session_id}_validated.json"

    def _safe_path(self, key: str) -> Path:
        cleaned = key.replace("\\", "/").lstrip("/")
        if ".." in cleaned.split("/"):
            raise ValidationAppError("Invalid storage key.")
        path = (self.root / cleaned).resolve()
        if not path.is_relative_to(self.root):
            raise ValidationAppError("Invalid storage key.")
        return path


# Backward-compatible alias used by older imports.
class LocalStorage(LocalStorageProvider):
    """Legacy helper methods retained for gradual migration."""

    def __init__(self, root: Path | None = None) -> None:
        super().__init__(root)
        self.imports_dir = self.root / "imports"
        self.template_images_dir = self.root / "template-images"
        self.imports_dir.mkdir(parents=True, exist_ok=True)
        self.template_images_dir.mkdir(parents=True, exist_ok=True)

    def import_file_path(self, stored_filename: str) -> Path:
        # stored_filename may already be a key like imports/uuid.csv
        if "/" in stored_filename:
            return self._safe_path(stored_filename)
        return self._safe_path(f"imports/{Path(stored_filename).name}")

    def template_image_path(self, stored_filename: str) -> Path:
        if "/" in stored_filename:
            return self._safe_path(stored_filename)
        return self._safe_path(f"template-images/{Path(stored_filename).name}")

    def validation_cache_path(self, session_id: str) -> Path:
        return self._safe_path(self.validation_cache_key(session_id))

    def write_bytes(self, relative_name: str, content: bytes) -> Path:
        key = relative_name if "/" in relative_name else f"imports/{Path(relative_name).name}"
        self.save(key, content)
        return self._safe_path(key)

    def read_bytes(self, stored_filename: str) -> bytes:
        if "/" in stored_filename:
            return self.read(stored_filename)
        return self.read(f"imports/{Path(stored_filename).name}")

    def save_import_file(self, content: bytes, extension: str) -> str:
        key = super().save_import_file(content, extension)
        # Legacy callers expect bare filename; keep basename for DB rows created before keys.
        return Path(key).name

    def save_template_image(self, content: bytes, extension: str) -> str:
        key = super().save_template_image(content, extension)
        return Path(key).name
