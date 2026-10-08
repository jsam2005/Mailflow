"""Storage abstraction tests."""

from __future__ import annotations

from pathlib import Path

from app.services.storage.local_provider import LocalStorageProvider


def test_local_storage_roundtrip(tmp_path: Path) -> None:
    provider = LocalStorageProvider(root=tmp_path)
    key = provider.save("imports/sample.csv", b"email\na@b.com\n", content_type="text/csv")
    assert provider.exists(key)
    assert provider.read(key) == b"email\na@b.com\n"
    assert provider.get_bytes(key) == b"email\na@b.com\n"
    provider.delete(key)
    assert not provider.exists(key)
