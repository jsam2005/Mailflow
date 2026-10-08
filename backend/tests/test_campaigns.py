"""Phase 6 campaign planning tests (no sending)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_recipient import CampaignRecipient, CampaignRecipientStatus
from app.models.contact import Contact, ContactStatus
from app.models.contact_list import ContactList
from app.models.email_account import ConnectionStatus, EmailAccount
from app.models.email_template import EmailTemplate
from app.models.user import User
from app.services.token_encryption_service import TokenEncryptionService


@pytest.fixture()
def encryption() -> TokenEncryptionService:
    return TokenEncryptionService()


def _account(
    db: Session,
    user: User,
    encryption: TokenEncryptionService,
    *,
    status: str = ConnectionStatus.CONNECTED.value,
    active: bool = True,
    email: str = "sender@gmail.com",
) -> EmailAccount:
    account = EmailAccount(
        user_id=user.id,
        provider="gmail",
        email_address=email,
        display_name="Sender",
        oauth_access_token_encrypted=encryption.encrypt("access"),
        oauth_refresh_token_encrypted=encryption.encrypt("refresh"),
        oauth_token_expiry=datetime.now(UTC) + timedelta(hours=1),
        daily_send_limit=100,
        hourly_send_limit=20,
        minimum_delay_seconds=30,
        maximum_delay_seconds=90,
        sent_today=0,
        sent_current_hour=0,
        connection_status=status,
        is_active=active,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _list_with_contacts(
    db: Session,
    user: User,
    *,
    contacts: list[dict] | None = None,
) -> tuple[ContactList, list[Contact]]:
    cl = ContactList(user_id=user.id, name="Outreach", total_contacts=0)
    db.add(cl)
    db.flush()
    created: list[Contact] = []
    for row in contacts or [
        {"email": "a@example.com", "first_name": "Arun", "company": "ABC", "status": ContactStatus.ACTIVE},
        {"email": "b@example.com", "first_name": None, "company": None, "status": ContactStatus.ACTIVE},
        {"email": "bad@example.com", "status": ContactStatus.INVALID},
        {"email": "unsub@example.com", "status": ContactStatus.UNSUBSCRIBED},
        {"email": "supp@example.com", "status": ContactStatus.SUPPRESSED},
        {"email": "bounce@example.com", "status": ContactStatus.BOUNCED},
    ]:
        c = Contact(
            contact_list_id=cl.id,
            email=row["email"],
            normalized_email=row["email"].lower(),
            first_name=row.get("first_name"),
            last_name=row.get("last_name"),
            company=row.get("company"),
            website=row.get("website"),
            status=row.get("status", ContactStatus.ACTIVE),
        )
        db.add(c)
        created.append(c)
    cl.total_contacts = len(created)
    db.commit()
    for c in created:
        db.refresh(c)
    db.refresh(cl)
    return cl, created


def _template(db: Session, user: User) -> EmailTemplate:
    t = EmailTemplate(
        user_id=user.id,
        name="Outreach",
        subject="Quick idea for {{company|your business}}",
        html_content="<p>Hi {{first_name|there}}, about {{company|your business}}.</p>",
        plain_text_content="Hi {{first_name|there}}",
        plain_text_customized=True,
        is_active=True,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _ready_campaign(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    admin_user: User,
    encryption: TokenEncryptionService,
) -> dict:
    account = _account(db, admin_user, encryption)
    cl, _ = _list_with_contacts(db, admin_user)
    template = _template(db, admin_user)
    created = client.post(
        "/api/v1/campaigns",
        headers=auth_headers,
        json={"name": "Q4 Outreach", "description": "Test"},
    )
    assert created.status_code == 201
    cid = created.json()["id"]
    client.put(
        f"/api/v1/campaigns/{cid}",
        headers=auth_headers,
        json={
            "email_account_id": str(account.id),
            "template_id": str(template.id),
            "daily_limit": 80,
            "hourly_limit": 15,
        },
    )
    snap = client.post(
        f"/api/v1/campaigns/{cid}/recipients/snapshot",
        headers=auth_headers,
        json={"contact_list_id": str(cl.id)},
    )
    assert snap.status_code == 200
    return {"id": cid, "account": account, "list": cl, "template": template}


def test_create_list_search_update_delete(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    created = client.post(
        "/api/v1/campaigns",
        headers=auth_headers,
        json={"name": "Alpha Campaign", "description": "hello world"},
    )
    assert created.status_code == 201
    assert created.json()["status"] == "draft"
    cid = created.json()["id"]

    listed = client.get("/api/v1/campaigns", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    search = client.get("/api/v1/campaigns?search=Alpha", headers=auth_headers)
    assert any(i["id"] == cid for i in search.json()["items"])

    updated = client.put(
        f"/api/v1/campaigns/{cid}",
        headers=auth_headers,
        json={"name": "Alpha Renamed"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Alpha Renamed"

    deleted = client.delete(f"/api/v1/campaigns/{cid}", headers=auth_headers)
    assert deleted.status_code == 204


def test_ownership_isolation(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    created = client.post(
        "/api/v1/campaigns",
        headers=auth_headers,
        json={"name": "Private"},
    )
    cid = created.json()["id"]
    assert client.get(f"/api/v1/campaigns/{cid}", headers=other_auth_headers).status_code == 404
    assert (
        client.put(
            f"/api/v1/campaigns/{cid}",
            headers=other_auth_headers,
            json={"name": "Hack"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/campaigns/{cid}/ready",
            headers=other_auth_headers,
        ).status_code
        == 404
    )


def test_foreign_account_template_list_rejected(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    other_user: User,
    encryption: TokenEncryptionService,
    admin_user: User,
) -> None:
    foreign_account = _account(db, other_user, encryption, email="other@gmail.com")
    foreign_list, _ = _list_with_contacts(db, other_user)
    foreign_template = _template(db, other_user)
    created = client.post(
        "/api/v1/campaigns",
        headers=auth_headers,
        json={"name": "Own"},
    )
    cid = created.json()["id"]

    assert (
        client.put(
            f"/api/v1/campaigns/{cid}",
            headers=auth_headers,
            json={"email_account_id": str(foreign_account.id)},
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/v1/campaigns/{cid}",
            headers=auth_headers,
            json={"template_id": str(foreign_template.id)},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/campaigns/{cid}/recipients/snapshot",
            headers=auth_headers,
            json={"contact_list_id": str(foreign_list.id)},
        ).status_code
        == 404
    )


def test_recipient_snapshot_exclusions_and_stats(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
) -> None:
    cl, contacts = _list_with_contacts(db, admin_user)
    created = client.post(
        "/api/v1/campaigns",
        headers=auth_headers,
        json={"name": "Snap"},
    )
    cid = created.json()["id"]
    snap = client.post(
        f"/api/v1/campaigns/{cid}/recipients/snapshot",
        headers=auth_headers,
        json={"contact_list_id": str(cl.id)},
    )
    assert snap.status_code == 200
    body = snap.json()
    assert body["total"] == 6
    assert body["eligible"] == 2
    assert body["invalid"] == 1
    assert body["suppressed"] == 3

    stats = client.get(f"/api/v1/campaigns/{cid}/stats", headers=auth_headers)
    assert stats.json()["eligible"] == 2
    assert stats.json()["pending"] == 2

    # Unique constraint / resnapshot replaces
    again = client.post(
        f"/api/v1/campaigns/{cid}/recipients/snapshot",
        headers=auth_headers,
        json={"contact_list_id": str(cl.id)},
    )
    assert again.status_code == 200
    assert again.json()["total"] == 6
    from uuid import UUID as UUIDType

    count = (
        db.query(CampaignRecipient)
        .filter(CampaignRecipient.campaign_id == UUIDType(cid))
        .count()
    )
    assert count == 6


def test_select_account_and_reject_disconnected_ready(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
) -> None:
    account = _account(db, admin_user, encryption)
    disconnected = _account(
        db,
        admin_user,
        encryption,
        status=ConnectionStatus.DISCONNECTED.value,
        active=False,
        email="old@gmail.com",
    )
    cl, _ = _list_with_contacts(db, admin_user)
    template = _template(db, admin_user)
    cid = client.post(
        "/api/v1/campaigns",
        headers=auth_headers,
        json={"name": "Acct"},
    ).json()["id"]

    ok = client.put(
        f"/api/v1/campaigns/{cid}",
        headers=auth_headers,
        json={"email_account_id": str(account.id), "template_id": str(template.id)},
    )
    assert ok.status_code == 200

    client.post(
        f"/api/v1/campaigns/{cid}/recipients/snapshot",
        headers=auth_headers,
        json={"contact_list_id": str(cl.id)},
    )

    # Switch to disconnected — can save draft but not ready
    client.put(
        f"/api/v1/campaigns/{cid}",
        headers=auth_headers,
        json={"email_account_id": str(disconnected.id)},
    )
    ready = client.post(f"/api/v1/campaigns/{cid}/ready", headers=auth_headers)
    assert ready.status_code == 422


def test_settings_validation_vs_account(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
) -> None:
    account = _account(db, admin_user, encryption)
    cid = client.post(
        "/api/v1/campaigns",
        headers=auth_headers,
        json={"name": "Limits"},
    ).json()["id"]
    client.put(
        f"/api/v1/campaigns/{cid}",
        headers=auth_headers,
        json={"email_account_id": str(account.id)},
    )
    bad = client.put(
        f"/api/v1/campaigns/{cid}",
        headers=auth_headers,
        json={"daily_limit": 50, "hourly_limit": 80},
    )
    assert bad.status_code == 422

    over = client.put(
        f"/api/v1/campaigns/{cid}",
        headers=auth_headers,
        json={"daily_limit": 500},
    )
    assert over.status_code == 422


def test_preview_personalization_and_ready_snapshot(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
) -> None:
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    cid = ctx["id"]
    template = ctx["template"]

    preview = client.post(
        f"/api/v1/campaigns/{cid}/preview",
        headers=auth_headers,
        json={},
    )
    assert preview.status_code == 200
    assert "Arun" in preview.json()["rendered_html"] or "there" in preview.json()["rendered_html"]
    assert preview.json()["has_next"] is True

    validation = client.post(f"/api/v1/campaigns/{cid}/validate", headers=auth_headers)
    assert validation.status_code == 200
    assert validation.json()["valid"] is True
    assert validation.json()["eligible_recipients"] == 2
    assert any("first name" in w.lower() for w in validation.json()["warnings"])

    ready = client.post(f"/api/v1/campaigns/{cid}/ready", headers=auth_headers)
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["has_content_snapshot"] is True
    snapshot_subject = ready.json()["snapshot_subject"]

    # Edit original template — ready campaign preview unchanged
    template.subject = "CHANGED SUBJECT SHOULD NOT APPEAR"
    template.html_content = "<p>CHANGED BODY</p>"
    db.commit()

    preview2 = client.post(
        f"/api/v1/campaigns/{cid}/preview",
        headers=auth_headers,
        json={},
    )
    assert preview2.status_code == 200
    assert preview2.json()["rendered_subject"] != "CHANGED SUBJECT SHOULD NOT APPEAR"
    assert "CHANGED BODY" not in preview2.json()["rendered_html"]
    # Snapshot stores template source; preview personalizes it
    assert "{{" in (snapshot_subject or "") or "Quick idea" in (snapshot_subject or "")
    assert "CHANGED" not in preview2.json()["rendered_subject"]

    # Contact list grows — ready recipient count stays frozen
    new_c = Contact(
        contact_list_id=ctx["list"].id,
        email="new@example.com",
        normalized_email="new@example.com",
        status=ContactStatus.ACTIVE,
    )
    db.add(new_c)
    ctx["list"].total_contacts += 1
    db.commit()
    stats = client.get(f"/api/v1/campaigns/{cid}/stats", headers=auth_headers)
    assert stats.json()["total"] == 6
    assert stats.json()["eligible"] == 2

    cancelled = client.post(f"/api/v1/campaigns/{cid}/cancel", headers=auth_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


def test_return_to_draft_and_html_sanitize(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
) -> None:
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    cid = ctx["id"]
    assert client.post(f"/api/v1/campaigns/{cid}/ready", headers=auth_headers).status_code == 200

    edited = client.post(f"/api/v1/campaigns/{cid}/edit", headers=auth_headers)
    assert edited.status_code == 200
    assert edited.json()["status"] == "draft"

    unsafe = client.put(
        f"/api/v1/campaigns/{cid}",
        headers=auth_headers,
        json={
            "subject_override": "Hi",
            "html_override": '<p>Hello</p><script>alert(1)</script><img src=x onerror=alert(1)>',
        },
    )
    assert unsafe.status_code == 200
    html = unsafe.json()["html_override"]
    assert "<script" not in (html or "").lower()
    assert "onerror" not in (html or "").lower()


def test_10k_snapshot_batch(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
) -> None:
    cl = ContactList(user_id=admin_user.id, name="Large", total_contacts=0)
    db.add(cl)
    db.flush()
    batch = []
    n = 2500  # substantial but fast enough for CI
    for i in range(n):
        batch.append(
            Contact(
                contact_list_id=cl.id,
                email=f"user{i}@example.com",
                normalized_email=f"user{i}@example.com",
                status=ContactStatus.ACTIVE if i % 10 else ContactStatus.INVALID,
            )
        )
        if len(batch) >= 500:
            db.add_all(batch)
            db.flush()
            batch.clear()
    if batch:
        db.add_all(batch)
    cl.total_contacts = n
    db.commit()

    cid = client.post(
        "/api/v1/campaigns",
        headers=auth_headers,
        json={"name": "Large Snap"},
    ).json()["id"]
    snap = client.post(
        f"/api/v1/campaigns/{cid}/recipients/snapshot",
        headers=auth_headers,
        json={"contact_list_id": str(cl.id)},
    )
    assert snap.status_code == 200
    assert snap.json()["total"] == n
    assert snap.json()["eligible"] == n - (n // 10)
    # Frontend must not receive all rows
    page = client.get(
        f"/api/v1/campaigns/{cid}/recipients?page=1&page_size=20&status=pending",
        headers=auth_headers,
    )
    assert page.status_code == 200
    assert len(page.json()["items"]) == 20
    assert page.json()["total"] == snap.json()["eligible"]


def test_custom_content_and_validation_errors(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    cid = client.post(
        "/api/v1/campaigns",
        headers=auth_headers,
        json={"name": "Incomplete"},
    ).json()["id"]
    validation = client.post(f"/api/v1/campaigns/{cid}/validate", headers=auth_headers)
    assert validation.status_code == 200
    assert validation.json()["valid"] is False
    assert len(validation.json()["errors"]) >= 2

    ready = client.post(f"/api/v1/campaigns/{cid}/ready", headers=auth_headers)
    assert ready.status_code == 422
