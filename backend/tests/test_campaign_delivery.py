"""Phase 7 campaign delivery engine tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_recipient import CampaignRecipient, CampaignRecipientStatus
from app.models.contact import Contact, ContactStatus
from app.models.email_message import EmailMessage, EmailMessageStatus
from app.services.email.base import SendResult
from app.services.token_encryption_service import TokenEncryptionService
from app.workers.campaign_sender_worker import CampaignSenderWorker
from tests.test_campaigns import _account, _list_with_contacts, _ready_campaign, _template


@pytest.fixture()
def encryption() -> TokenEncryptionService:
    return TokenEncryptionService()


def _mark_ready(client: TestClient, auth_headers: dict[str, str], cid: str) -> None:
    assert client.post(f"/api/v1/campaigns/{cid}/ready", headers=auth_headers).status_code == 200


def test_start_ready_campaign_creates_messages(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user,
    encryption: TokenEncryptionService,
) -> None:
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    _mark_ready(client, auth_headers, ctx["id"])
    started = client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers)
    assert started.status_code == 200
    assert started.json()["status"] == "running"
    cid = UUID(ctx["id"])
    messages = db.query(EmailMessage).filter(EmailMessage.campaign_id == cid).all()
    assert len(messages) == 2
    assert all(m.status == EmailMessageStatus.QUEUED.value for m in messages)
    queued_recipients = db.query(CampaignRecipient).filter(
        CampaignRecipient.campaign_id == cid,
        CampaignRecipient.status == CampaignRecipientStatus.QUEUED.value,
    ).count()
    assert queued_recipients == 2


def test_reject_start_draft(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    cid = client.post(
        "/api/v1/campaigns",
        headers=auth_headers,
        json={"name": "Draft only"},
    ).json()["id"]
    resp = client.post(f"/api/v1/campaigns/{cid}/start", headers=auth_headers)
    assert resp.status_code == 422


def test_reject_start_cancelled(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user,
    encryption: TokenEncryptionService,
) -> None:
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    _mark_ready(client, auth_headers, ctx["id"])
    client.post(f"/api/v1/campaigns/{ctx['id']}/cancel", headers=auth_headers)
    resp = client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers)
    assert resp.status_code == 422


def test_idempotent_start_conflict(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user,
    encryption: TokenEncryptionService,
) -> None:
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    _mark_ready(client, auth_headers, ctx["id"])
    assert client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers).status_code == 200
    again = client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers)
    assert again.status_code == 409
    assert db.query(EmailMessage).filter(EmailMessage.campaign_id == UUID(ctx["id"])).count() == 2


def test_sending_disabled(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user,
    encryption: TokenEncryptionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CAMPAIGN_SENDING_ENABLED", "false")
    get_settings.cache_clear()
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    _mark_ready(client, auth_headers, ctx["id"])
    resp = client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers)
    assert resp.status_code == 503
    get_settings.cache_clear()


def test_worker_sends_mock_gmail(
    db: Session,
    admin_user,
    encryption: TokenEncryptionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _account(db, admin_user, encryption, email="worker@gmail.com")
    cl, contacts = _list_with_contacts(
        db,
        admin_user,
        contacts=[
            {"email": "send@example.com", "first_name": "Sam", "company": "Co", "status": ContactStatus.ACTIVE},
        ],
    )
    template = _template(db, admin_user)
    campaign = Campaign(
        user_id=admin_user.id,
        name="Worker test",
        status=CampaignStatus.RUNNING.value,
        email_account_id=account.id,
        template_id=template.id,
        contact_list_id=cl.id,
        snapshot_subject=template.subject,
        snapshot_html=template.html_content,
        snapshot_plain_text=template.plain_text_content,
        daily_limit=80,
        hourly_limit=15,
        minimum_delay_seconds=30,
        maximum_delay_seconds=90,
        started_at=datetime.now(UTC),
    )
    db.add(campaign)
    db.flush()
    contact = contacts[0]
    recipient = CampaignRecipient(
        campaign_id=campaign.id,
        contact_id=contact.id,
        status=CampaignRecipientStatus.QUEUED.value,
    )
    db.add(recipient)
    db.flush()
    message = EmailMessage(
        user_id=admin_user.id,
        campaign_id=campaign.id,
        campaign_recipient_id=recipient.id,
        contact_id=contact.id,
        email_account_id=account.id,
        to_email=contact.email,
        to_name="Sam",
        subject=template.subject,
        rendered_html=template.html_content,
        rendered_text=template.plain_text_content,
        status=EmailMessageStatus.QUEUED.value,
        next_attempt_at=datetime.now(UTC),
    )
    db.add(message)
    db.commit()

    gmail = MagicMock()
    gmail.send_raw_message.return_value = SendResult(
        provider_message_id="gmail-msg-1",
        provider_thread_id="thread-1",
    )
    monkeypatch.setattr(
        "app.services.email_account_service.EmailAccountService._get_valid_access_token",
        lambda self, acc: "fake-token",
    )

    worker = CampaignSenderWorker(db, gmail=gmail)
    worker.tick()
    db.refresh(message)
    db.refresh(recipient)
    db.refresh(campaign)

    assert message.status == EmailMessageStatus.SENT.value
    assert message.provider_message_id == "gmail-msg-1"
    assert message.rfc_message_id
    assert recipient.status == CampaignRecipientStatus.SENT.value
    assert account.next_send_allowed_at is not None
    gmail.send_raw_message.assert_called_once()


def test_pause_and_resume(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user,
    encryption: TokenEncryptionService,
) -> None:
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    _mark_ready(client, auth_headers, ctx["id"])
    client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers)
    paused = client.post(f"/api/v1/campaigns/{ctx['id']}/pause", headers=auth_headers)
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    resumed = client.post(f"/api/v1/campaigns/{ctx['id']}/resume", headers=auth_headers)
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "running"


def test_cancel_running_preserves_sent(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user,
    encryption: TokenEncryptionService,
) -> None:
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    _mark_ready(client, auth_headers, ctx["id"])
    client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers)
    cid = UUID(ctx["id"])
    msg = db.query(EmailMessage).filter(EmailMessage.campaign_id == cid).first()
    assert msg
    msg.status = EmailMessageStatus.SENT.value
    msg.sent_at = datetime.now(UTC)
    db.commit()
    cancelled = client.post(f"/api/v1/campaigns/{ctx['id']}/cancel", headers=auth_headers)
    assert cancelled.status_code == 200
    db.refresh(msg)
    assert msg.status == EmailMessageStatus.SENT.value
    remaining = db.query(EmailMessage).filter(
        EmailMessage.campaign_id == cid,
        EmailMessage.status == EmailMessageStatus.CANCELLED.value,
    ).count()
    assert remaining == 1


def test_stale_sending_recovery(
    db: Session,
    admin_user,
    encryption: TokenEncryptionService,
) -> None:
    account = _account(db, admin_user, encryption)
    campaign = Campaign(
        user_id=admin_user.id,
        name="Stale",
        status=CampaignStatus.RUNNING.value,
        email_account_id=account.id,
        snapshot_subject="Hi",
        snapshot_html="<p>Hi</p>",
        started_at=datetime.now(UTC),
    )
    db.add(campaign)
    db.flush()
    recipient = CampaignRecipient(
        campaign_id=campaign.id,
        contact_id=_list_with_contacts(db, admin_user)[1][0].id,
        status=CampaignRecipientStatus.QUEUED.value,
    )
    db.add(recipient)
    db.flush()
    message = EmailMessage(
        user_id=admin_user.id,
        campaign_id=campaign.id,
        campaign_recipient_id=recipient.id,
        contact_id=recipient.contact_id,
        email_account_id=account.id,
        to_email="a@example.com",
        subject="Hi",
        rendered_html="<p>Hi</p>",
        status=EmailMessageStatus.SENDING.value,
        last_attempt_at=datetime.now(UTC) - timedelta(minutes=30),
        attempt_count=1,
    )
    db.add(message)
    db.commit()
    CampaignSenderWorker(db).tick()
    db.refresh(message)
    assert message.status == EmailMessageStatus.FAILED.value
    assert message.error_code == "UNCERTAIN_PROVIDER_RESULT"


def test_manual_retry_blocked_uncertain(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user,
    encryption: TokenEncryptionService,
) -> None:
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    _mark_ready(client, auth_headers, ctx["id"])
    client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers)
    msg = db.query(EmailMessage).filter(EmailMessage.campaign_id == UUID(ctx["id"])).first()
    msg.status = EmailMessageStatus.FAILED.value
    msg.error_code = "UNCERTAIN_PROVIDER_RESULT"
    db.commit()
    resp = client.post(
        f"/api/v1/campaigns/{ctx['id']}/messages/{msg.id}/retry",
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_message_list_and_ownership(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
    admin_user,
    encryption: TokenEncryptionService,
) -> None:
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    _mark_ready(client, auth_headers, ctx["id"])
    client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers)
    listed = client.get(f"/api/v1/campaigns/{ctx['id']}/messages", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 2
    assert client.get(
        f"/api/v1/campaigns/{ctx['id']}/messages",
        headers=other_auth_headers,
    ).status_code == 404


def test_worker_claim_atomic(
    db: Session,
    admin_user,
    encryption: TokenEncryptionService,
) -> None:
    account = _account(db, admin_user, encryption)
    campaign = Campaign(
        user_id=admin_user.id,
        name="Claim",
        status=CampaignStatus.RUNNING.value,
        email_account_id=account.id,
        snapshot_subject="S",
        snapshot_html="<p>x</p>",
        started_at=datetime.now(UTC),
    )
    db.add(campaign)
    db.flush()
    _, contacts = _list_with_contacts(db, admin_user, contacts=[
        {"email": "x@example.com", "status": ContactStatus.ACTIVE},
    ])
    recipient = CampaignRecipient(
        campaign_id=campaign.id,
        contact_id=contacts[0].id,
        status=CampaignRecipientStatus.QUEUED.value,
    )
    db.add(recipient)
    db.flush()
    message = EmailMessage(
        user_id=admin_user.id,
        campaign_id=campaign.id,
        campaign_recipient_id=recipient.id,
        contact_id=contacts[0].id,
        email_account_id=account.id,
        to_email="x@example.com",
        subject="S",
        rendered_html="<p>x</p>",
        status=EmailMessageStatus.QUEUED.value,
        next_attempt_at=datetime.now(UTC),
    )
    db.add(message)
    db.commit()

    w1 = CampaignSenderWorker(db)
    w2 = CampaignSenderWorker(db)
    assert w1._claim_message(db, message) is True
    db.refresh(message)
    assert message.status == EmailMessageStatus.SENDING.value
    assert w2._claim_message(db, message) is False


def test_suppression_recheck(
    db: Session,
    admin_user,
    encryption: TokenEncryptionService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _account(db, admin_user, encryption)
    _, contacts = _list_with_contacts(db, admin_user, contacts=[
        {"email": "gone@example.com", "status": ContactStatus.ACTIVE},
    ])
    contact = contacts[0]
    campaign = Campaign(
        user_id=admin_user.id,
        name="Supp",
        status=CampaignStatus.RUNNING.value,
        email_account_id=account.id,
        snapshot_subject="Hi {{first_name|there}}",
        snapshot_html="<p>Hi</p>",
        started_at=datetime.now(UTC),
    )
    db.add(campaign)
    db.flush()
    recipient = CampaignRecipient(
        campaign_id=campaign.id,
        contact_id=contact.id,
        status=CampaignRecipientStatus.QUEUED.value,
    )
    db.add(recipient)
    db.flush()
    message = EmailMessage(
        user_id=admin_user.id,
        campaign_id=campaign.id,
        campaign_recipient_id=recipient.id,
        contact_id=contact.id,
        email_account_id=account.id,
        to_email=contact.email,
        subject="Hi",
        rendered_html="<p>Hi</p>",
        status=EmailMessageStatus.QUEUED.value,
        next_attempt_at=datetime.now(UTC),
    )
    db.add(message)
    contact.status = ContactStatus.UNSUBSCRIBED
    db.commit()

    worker = CampaignSenderWorker(db, gmail=MagicMock())
    worker.tick()
    db.refresh(message)
    db.refresh(recipient)
    assert message.status == EmailMessageStatus.CANCELLED.value
    assert message.error_code == "RECIPIENT_NO_LONGER_ELIGIBLE"
    assert recipient.status == CampaignRecipientStatus.SUPPRESSED.value
