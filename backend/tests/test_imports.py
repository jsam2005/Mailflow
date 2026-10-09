"""Contact import API and service tests."""

from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

FIXTURES = Path(__file__).parent / "fixtures"

SAMPLE_MAPPING = {
    "Mail ID": "email",
    "Contact Person": "full_name",
    "Business Name": "company",
    "Mobile": "phone",
    "City": "custom",
    "Industry": "custom",
}


def _upload(client: TestClient, headers: dict[str, str], filename: str) -> dict:
    path = FIXTURES / filename
    with path.open("rb") as handle:
        response = client.post(
            "/api/v1/imports/upload",
            headers=headers,
            files={"file": (filename, handle, "application/octet-stream")},
        )
    assert response.status_code == 200, response.text
    return response.json()


def _create_list(client: TestClient, headers: dict[str, str], name: str = "Import List") -> dict:
    response = client.post(
        "/api/v1/contact-lists",
        headers=headers,
        json={"name": name},
    )
    assert response.status_code == 201
    return response.json()


def test_csv_upload_preview_and_suggestions(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    data = _upload(client, auth_headers, "contacts_sample.csv")
    assert data["file_type"] == "csv"
    assert data["total_rows"] == 6
    assert "Mail ID" in data["columns"]
    assert data["suggested_mapping"]["Mail ID"] == "email"
    assert data["suggested_mapping"]["Contact Person"] == "full_name"
    assert len(data["preview_rows"]) <= 20


def test_xlsx_upload(client: TestClient, auth_headers: dict[str, str]) -> None:
    data = _upload(client, auth_headers, "contacts_sample.xlsx")
    assert data["file_type"] == "xlsx"
    assert "Leads" in data["sheets"]
    assert data["default_sheet"] == "Leads"
    assert data["total_rows"] >= 5


def test_reject_unsupported_extension(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    response = client.post(
        "/api/v1/imports/upload",
        headers=auth_headers,
        files={"file": ("notes.txt", BytesIO(b"hello"), "text/plain")},
    )
    assert response.status_code == 422
    assert "CSV or XLSX" in response.json()["message"]


def test_reject_oversized_file(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    from app.core.config import Settings
    import app.services.import_service.service as import_service_module

    settings = Settings(max_import_file_mb=0)
    monkeypatch.setattr(import_service_module, "get_settings", lambda: settings)

    response = client.post(
        "/api/v1/imports/upload",
        headers=auth_headers,
        files={"file": ("big.csv", BytesIO(b"email\na@b.com\n"), "text/csv")},
    )
    assert response.status_code == 422
    assert "MB" in response.json()["message"]


def test_validate_and_execute_import(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    contact_list = _create_list(client, auth_headers)
    uploaded = _upload(client, auth_headers, "contacts_sample.csv")
    import_id = uploaded["import_session_id"]

    validated = client.post(
        f"/api/v1/imports/{import_id}/validate",
        headers=auth_headers,
        json={
            "column_mapping": SAMPLE_MAPPING,
            "contact_list_id": contact_list["id"],
        },
    )
    assert validated.status_code == 200, validated.text
    summary = validated.json()
    assert summary["total_rows"] == 6
    assert summary["invalid_email_rows"] == 1
    assert summary["missing_email_rows"] == 1
    assert summary["duplicate_in_file_rows"] == 1
    assert summary["importable_rows"] == 3

    executed = client.post(
        f"/api/v1/imports/{import_id}/execute",
        headers=auth_headers,
        json={
            "contact_list_id": contact_list["id"],
            "column_mapping": SAMPLE_MAPPING,
        },
    )
    assert executed.status_code == 200, executed.text
    body = executed.json()
    assert body["imported_rows"] == 3
    assert body["status"] == "completed"

    # Second execute must not clobber completed status or re-import.
    again = client.post(
        f"/api/v1/imports/{import_id}/execute",
        headers=auth_headers,
        json={
            "contact_list_id": contact_list["id"],
            "column_mapping": SAMPLE_MAPPING,
        },
    )
    assert again.status_code == 422
    assert "already been completed" in again.json()["message"]
    status = client.get(f"/api/v1/imports/{import_id}", headers=auth_headers)
    assert status.json()["status"] == "completed"

    contacts = client.get(
        "/api/v1/contacts",
        headers=auth_headers,
        params={"contact_list_id": contact_list["id"]},
    )
    assert contacts.json()["total"] == 3

    # Metadata custom fields
    arun = next(item for item in contacts.json()["items"] if "arun@" in item["email"].lower())
    assert arun["first_name"] == "Arun"
    assert arun["last_name"] == "Kumar"
    assert arun["company"] == "ABC Ltd"
    assert arun["metadata"]["City"] == "Chennai"
    assert arun["metadata"]["Industry"] == "Construction"

    lists = client.get("/api/v1/contact-lists", headers=auth_headers)
    assert lists.json()[0]["total_contacts"] == 3


def test_duplicate_existing_skipped_on_reimport(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    contact_list = _create_list(client, auth_headers, "List A")
    first = _upload(client, auth_headers, "contacts_sample.csv")
    client.post(
        f"/api/v1/imports/{first['import_session_id']}/execute",
        headers=auth_headers,
        json={"contact_list_id": contact_list["id"], "column_mapping": SAMPLE_MAPPING},
    )

    second = _upload(client, auth_headers, "contacts_sample.csv")
    validated = client.post(
        f"/api/v1/imports/{second['import_session_id']}/validate",
        headers=auth_headers,
        json={
            "column_mapping": SAMPLE_MAPPING,
            "contact_list_id": contact_list["id"],
        },
    )
    summary = validated.json()
    assert summary["duplicate_existing_rows"] == 3
    assert summary["importable_rows"] == 0

    blocked = client.post(
        f"/api/v1/imports/{second['import_session_id']}/execute",
        headers=auth_headers,
        json={"contact_list_id": contact_list["id"], "column_mapping": SAMPLE_MAPPING},
    )
    assert blocked.status_code == 422


def test_same_emails_allowed_in_different_lists(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    list_a = _create_list(client, auth_headers, "A")
    list_b = _create_list(client, auth_headers, "B")
    first = _upload(client, auth_headers, "contacts_sample.csv")
    client.post(
        f"/api/v1/imports/{first['import_session_id']}/execute",
        headers=auth_headers,
        json={"contact_list_id": list_a["id"], "column_mapping": SAMPLE_MAPPING},
    )
    second = _upload(client, auth_headers, "contacts_sample.csv")
    executed = client.post(
        f"/api/v1/imports/{second['import_session_id']}/execute",
        headers=auth_headers,
        json={"contact_list_id": list_b["id"], "column_mapping": SAMPLE_MAPPING},
    )
    assert executed.status_code == 200
    assert executed.json()["imported_rows"] == 3


def test_email_mapping_required(client: TestClient, auth_headers: dict[str, str]) -> None:
    uploaded = _upload(client, auth_headers, "contacts_sample.csv")
    response = client.post(
        f"/api/v1/imports/{uploaded['import_session_id']}/validate",
        headers=auth_headers,
        json={"column_mapping": {"City": "custom"}},
    )
    assert response.status_code == 422
    assert "Email" in response.json()["message"]


def test_cancel_import(client: TestClient, auth_headers: dict[str, str]) -> None:
    uploaded = _upload(client, auth_headers, "contacts_sample.csv")
    response = client.post(
        f"/api/v1/imports/{uploaded['import_session_id']}/cancel",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_import_history_and_detail(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    contact_list = _create_list(client, auth_headers)
    uploaded = _upload(client, auth_headers, "contacts_sample.csv")
    client.post(
        f"/api/v1/imports/{uploaded['import_session_id']}/execute",
        headers=auth_headers,
        json={"contact_list_id": contact_list["id"], "column_mapping": SAMPLE_MAPPING},
    )
    history = client.get("/api/v1/imports", headers=auth_headers)
    assert history.status_code == 200
    assert len(history.json()) >= 1

    detail = client.get(
        f"/api/v1/imports/{uploaded['import_session_id']}",
        headers=auth_headers,
    )
    assert detail.status_code == 200
    assert detail.json()["imported_rows"] == 3


def test_cross_user_import_access_denied(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    uploaded = _upload(client, auth_headers, "contacts_sample.csv")
    response = client.get(
        f"/api/v1/imports/{uploaded['import_session_id']}",
        headers=other_auth_headers,
    )
    assert response.status_code == 404


def test_execute_with_new_list(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    uploaded = _upload(client, auth_headers, "contacts_sample.csv")
    response = client.post(
        f"/api/v1/imports/{uploaded['import_session_id']}/execute",
        headers=auth_headers,
        json={
            "new_list_name": "Fresh Import List",
            "new_list_description": "Created during import",
            "column_mapping": SAMPLE_MAPPING,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["imported_rows"] == 3
    assert response.json()["contact_list_name"] == "Fresh Import List"


def test_column_detection_unit() -> None:
    from app.services.import_service.column_mapping import suggest_column_mapping, split_full_name

    mapping = suggest_column_mapping(["Mail ID", "Business Name", "City"])
    assert mapping["Mail ID"] == "email"
    assert mapping["Business Name"] == "company"
    assert "City" not in mapping

    first, last = split_full_name("Selva Muthu Kumaran")
    assert first == "Selva"
    assert last == "Muthu Kumaran"
