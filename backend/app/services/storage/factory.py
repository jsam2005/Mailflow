"""Storage provider factory."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.storage.base import StorageProvider
from app.services.storage.local_provider import LocalStorageProvider
from app.services.storage.vercel_blob import VercelBlobStorageProvider


@lru_cache
def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    provider = (settings.storage_provider or "local").strip().lower()
    if provider == "vercel_blob":
        return VercelBlobStorageProvider()
    return LocalStorageProvider()


def resolve_asset_key(
    *,
    storage_key: str | None,
    stored_filename: str | None,
    kind: str = "template-images",
) -> str:
    """Resolve a storage key from new or legacy asset fields."""
    if storage_key:
        return storage_key
    if not stored_filename:
        raise ValueError("Missing storage key")
    if "/" in stored_filename:
        return stored_filename
    return f"{kind}/{stored_filename}"
