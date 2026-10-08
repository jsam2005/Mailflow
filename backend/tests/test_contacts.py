"""Contact list and contact CRUD tests."""

from fastapi.testclient import TestClient


def _create_list(client: TestClient, headers: dict[str, str], name: str = "Leads") -> dict:
    response = client.post(
        "/api/v1/contact-lists",
        headers=headers,
        json={"name": name, "description": "Test list"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_contact(
    client: TestClient,
    headers: dict[str, str],
    list_id: str,
    email: str,
    **extra: object,
) -> dict:
    payload = {"email": email, **extra}
    response = client.post(
        f"/api/v1/contact-lists/{list_id}/contacts",
        headers=headers,
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_list_contact_lists(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = _create_list(client, auth_headers, "Outbound Q1")
    assert created["name"] == "Outbound Q1"
    assert created["total_contacts"] == 0

    response = client.get("/api/v1/contact-lists", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_update_and_delete_contact_list(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = _create_list(client, auth_headers)
    list_id = created["id"]

    updated = client.put(
        f"/api/v1/contact-lists/{list_id}",
        headers=auth_headers,
        json={"name": "Renamed", "description": "Updated"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed"

    deleted = client.delete(f"/api/v1/contact-lists/{list_id}", headers=auth_headers)
    assert deleted.status_code == 204

    missing = client.get(f"/api/v1/contact-lists/{list_id}", headers=auth_headers)
    assert missing.status_code == 404


def test_create_contact_and_normalize_email(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    contact_list = _create_list(client, auth_headers)
    contact = _create_contact(
        client,
        auth_headers,
        contact_list["id"],
        "  Alex@Example.COM ",
        first_name="Alex",
        last_name="Rivera",
        company="Acme",
    )
    assert contact["email"].lower() == "alex@example.com"
    assert contact["first_name"] == "Alex"
    assert contact["contact_list_name"] == "Leads" or contact["contact_list_id"] == contact_list["id"]

    listed = client.get("/api/v1/contact-lists", headers=auth_headers)
    assert listed.json()[0]["total_contacts"] == 1


def test_reject_invalid_email(client: TestClient, auth_headers: dict[str, str]) -> None:
    contact_list = _create_list(client, auth_headers)
    response = client.post(
        f"/api/v1/contact-lists/{contact_list['id']}/contacts",
        headers=auth_headers,
        json={"email": "not-an-email"},
    )
    assert response.status_code == 422


def test_prevent_duplicate_email_same_list(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    contact_list = _create_list(client, auth_headers)
    _create_contact(client, auth_headers, contact_list["id"], "dup@example.com")
    response = client.post(
        f"/api/v1/contact-lists/{contact_list['id']}/contacts",
        headers=auth_headers,
        json={"email": "DUP@example.com"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "conflict"


def test_allow_same_email_different_lists(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    list_a = _create_list(client, auth_headers, "List A")
    list_b = _create_list(client, auth_headers, "List B")
    _create_contact(client, auth_headers, list_a["id"], "shared@example.com")
    contact_b = _create_contact(client, auth_headers, list_b["id"], "shared@example.com")
    assert contact_b["email"].lower() == "shared@example.com"


def test_list_contacts_pagination_search_filter_sort(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    contact_list = _create_list(client, auth_headers)
    list_id = contact_list["id"]
    _create_contact(client, auth_headers, list_id, "anna@acme.com", first_name="Anna", company="Acme")
    _create_contact(client, auth_headers, list_id, "bob@beta.com", first_name="Bob", company="Beta")
    _create_contact(client, auth_headers, list_id, "cara@acme.com", first_name="Cara", company="Acme")

    page = client.get(
        "/api/v1/contacts",
        headers=auth_headers,
        params={"page": 1, "page_size": 2, "sort_by": "first_name", "sort_order": "asc"},
    )
    assert page.status_code == 200
    body = page.json()
    assert body["total"] == 3
    assert body["page_size"] == 2
    assert body["total_pages"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["first_name"] == "Anna"

    search = client.get(
        "/api/v1/contacts",
        headers=auth_headers,
        params={"search": "acme"},
    )
    assert search.json()["total"] == 2

    filtered = client.get(
        "/api/v1/contacts",
        headers=auth_headers,
        params={"company": "Beta", "contact_list_id": list_id},
    )
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["first_name"] == "Bob"


def test_update_and_delete_contact(client: TestClient, auth_headers: dict[str, str]) -> None:
    contact_list = _create_list(client, auth_headers)
    contact = _create_contact(
        client,
        auth_headers,
        contact_list["id"],
        "edit@example.com",
        first_name="Ed",
    )

    updated = client.put(
        f"/api/v1/contacts/{contact['id']}",
        headers=auth_headers,
        json={"first_name": "Eddie", "status": "suppressed", "company": "NewCo"},
    )
    assert updated.status_code == 200
    assert updated.json()["first_name"] == "Eddie"
    assert updated.json()["status"] == "suppressed"

    deleted = client.delete(f"/api/v1/contacts/{contact['id']}", headers=auth_headers)
    assert deleted.status_code == 204

    lists = client.get("/api/v1/contact-lists", headers=auth_headers)
    assert lists.json()[0]["total_contacts"] == 0


def test_bulk_delete_contacts(client: TestClient, auth_headers: dict[str, str]) -> None:
    contact_list = _create_list(client, auth_headers)
    c1 = _create_contact(client, auth_headers, contact_list["id"], "a@example.com")
    c2 = _create_contact(client, auth_headers, contact_list["id"], "b@example.com")

    response = client.post(
        "/api/v1/contacts/bulk-delete",
        headers=auth_headers,
        json={"contact_ids": [c1["id"], c2["id"]]},
    )
    assert response.status_code == 200
    assert response.json()["deleted"] == 2

    listed = client.get("/api/v1/contacts", headers=auth_headers)
    assert listed.json()["total"] == 0


def test_delete_list_cascades_contacts(client: TestClient, auth_headers: dict[str, str]) -> None:
    contact_list = _create_list(client, auth_headers)
    _create_contact(client, auth_headers, contact_list["id"], "gone@example.com")

    deleted = client.delete(
        f"/api/v1/contact-lists/{contact_list['id']}",
        headers=auth_headers,
    )
    assert deleted.status_code == 204

    contacts = client.get("/api/v1/contacts", headers=auth_headers)
    assert contacts.json()["total"] == 0


def test_contact_stats(client: TestClient, auth_headers: dict[str, str]) -> None:
    list_a = _create_list(client, auth_headers, "A")
    _create_contact(client, auth_headers, list_a["id"], "one@example.com")
    contact = _create_contact(client, auth_headers, list_a["id"], "two@example.com")
    client.put(
        f"/api/v1/contacts/{contact['id']}",
        headers=auth_headers,
        json={"status": "unsubscribed"},
    )

    stats = client.get("/api/v1/contacts/stats", headers=auth_headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["total"] == 2
    assert body["active"] == 1
    assert body["unsubscribed"] == 1
    assert body["contact_lists"] == 1


def test_user_cannot_access_other_users_lists(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    owned = _create_list(client, auth_headers, "Private")
    response = client.get(
        f"/api/v1/contact-lists/{owned['id']}",
        headers=other_auth_headers,
    )
    assert response.status_code == 404


def test_user_cannot_access_other_users_contacts(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    owned_list = _create_list(client, auth_headers)
    contact = _create_contact(client, auth_headers, owned_list["id"], "secret@example.com")

    response = client.get(
        f"/api/v1/contacts/{contact['id']}",
        headers=other_auth_headers,
    )
    assert response.status_code == 404

    listed = client.get("/api/v1/contacts", headers=other_auth_headers)
    assert listed.json()["total"] == 0


def test_contacts_require_auth(client: TestClient) -> None:
    assert client.get("/api/v1/contacts").status_code == 401
    assert client.get("/api/v1/contact-lists").status_code == 401
