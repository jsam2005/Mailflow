"""Local storage (re-export for backward compatibility)."""

from app.services.storage.local_provider import LocalStorage, LocalStorageProvider

__all__ = ["LocalStorage", "LocalStorageProvider"]
