"""Storage provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO
from uuid import uuid4


class StorageProvider(ABC):
    """Neutral interface for local and cloud object storage."""

    name: str

    @abstractmethod
    def save(self, key: str, content: bytes, *, content_type: str | None = None) -> str:
        """Persist bytes under key. Returns storage key."""

    @abstractmethod
    def read(self, key: str) -> bytes:
        """Read object bytes."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete object if present."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if object exists."""

    def get_url(self, key: str) -> str | None:
        """Optional public/signed URL. Local storage returns None."""
        return None

    def get_bytes(self, key: str) -> bytes:
        return self.read(key)

    def save_stream(
        self,
        key: str,
        stream: BinaryIO,
        *,
        content_type: str | None = None,
    ) -> str:
        return self.save(key, stream.read(), content_type=content_type)

    def save_import_file(self, content: bytes, extension: str) -> str:
        key = f"imports/{uuid4()}.{extension.lower().lstrip('.')}"
        return self.save(key, content)

    def save_template_image(self, content: bytes, extension: str) -> str:
        key = f"template-images/{uuid4()}.{extension.lower().lstrip('.')}"
        return self.save(key, content)
