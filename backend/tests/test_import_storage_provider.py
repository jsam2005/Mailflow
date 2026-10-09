"""Import upload must work via StorageProvider without local disk paths."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import ValidationAppError
from app.services.import_service.parsers import get_parser
from app.services.storage.base import StorageProvider
from app.services.storage.local_provider import LocalStorageProvider


class MemoryStorageProvider(StorageProvider):
    name = "memory"

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def save(self, key: str, content: bytes, *, content_type: str | None = None) -> str:
        self.objects[key] = content
        return key

    def read(self, key: str) -> bytes:
        if key not in self.objects:
            raise ValidationAppError("missing")
        return self.objects[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)

    def exists(self, key: str) -> bool:
        return key in self.objects


def test_csv_parser_from_bytes() -> None:
    data = b"email,first_name\ntest@example.com,Test\n"
    parser = get_parser(data, "csv")
    assert parser.get_columns() == ["email", "first_name"]
    assert parser.get_row_count() == 1
    assert parser.get_preview()[0]["email"] == "test@example.com"


def test_csv_parser_utf8_bom() -> None:
    data = b"\xef\xbb\xbfemail,first_name\ntest@example.com,Test\n"
    parser = get_parser(data, "csv")
    assert parser.get_columns() == ["email", "first_name"]


def test_xlsx_parser_from_bytes(tmp_path: Path) -> None:
    # Build a tiny xlsx via openpyxl then parse as bytes
    from openpyxl import Workbook

    path = tmp_path / "one.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["email", "first_name"])
    ws.append(["xlsx@example.com", "X"])
    wb.save(path)
    parser = get_parser(path.read_bytes(), "xlsx")
    assert parser.get_sheets() == ["Sheet1"]
    assert parser.get_row_count() == 1


def test_import_upload_uses_injected_storage(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
    tmp_path: Path,
) -> None:
    provider = LocalStorageProvider(root=tmp_path)
    monkeypatch.setattr(
        "app.services.import_service.service.get_storage_provider",
        lambda: provider,
    )
    # Clear factory cache if used elsewhere
    from app.services.storage import factory as storage_factory

    storage_factory.get_storage_provider.cache_clear()

    response = client.post(
        "/api/v1/imports/upload",
        headers=auth_headers,
        files={
            "file": (
                "tiny.csv",
                BytesIO(b"email,first_name,company\ntest-controlled-address@example.com,Test,MailFlow Test\n"),
                "text/csv",
            )
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_rows"] == 1
    assert "email" in body["columns"]
    stored = next(tmp_path.joinpath("imports").glob("*.csv"))
    assert stored.read_bytes().startswith(b"email")


def test_blob_save_failure_returns_safe_error(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    class FailingStorage(MemoryStorageProvider):
        def save_import_file(self, content: bytes, extension: str) -> str:
            raise RuntimeError("blob down")

    monkeypatch.setattr(
        "app.services.import_service.service.get_storage_provider",
        lambda: FailingStorage(),
    )
    from app.services.storage import factory as storage_factory

    storage_factory.get_storage_provider.cache_clear()

    response = client.post(
        "/api/v1/imports/upload",
        headers=auth_headers,
        files={
            "file": (
                "tiny.csv",
                BytesIO(b"email\na@b.com\n"),
                "text/csv",
            )
        },
    )
    assert response.status_code == 422
    assert "Could not process this contact file." in response.json()["message"]
