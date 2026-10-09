"""Campaign personalization, preview-after-queue, and worker claim safety."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.campaign import CampaignStatus
from app.models.campaign_recipient import CampaignRecipient, CampaignRecipientStatus
from app.models.email_message import EmailMessage, EmailMessageStatus
from app.services.campaign.personalization import (
    UnresolvedPersonalizationError,
    render_campaign_content,
)
from app.services.email.base import SendResult
from app.services.template_render_service import RenderContext, TemplateRenderService
from app.services.token_encryption_service import TokenEncryptionService
from app.workers.campaign_sender_worker import CampaignSenderWorker
from tests.test_campaigns import _ready_campaign
from tests.test_campaign_delivery import _mark_ready


def test_render_fallbacks_and_rejects_unresolved() -> None:
    result = render_campaign_content(
        subject="Hi {{first_name|there}} at {{company|your business}}",
        html="<p>Dear {{first_name|there}}</p>",
        text="Dear {{first_name|there}}",
        contact=None,
        fallback_email="a@example.com",
        require_resolved=True,
    )
    assert result.rendered_subject == "Hi there at your business"
    assert "there" in result.rendered_html
    assert not TemplateRenderService.has_unresolved_tokens(
        result.rendered_subject, result.rendered_html, result.rendered_text
    )

    # Malformed leftover brace content is detected by the scanner when present.
    assert TemplateRenderService.has_unresolved_tokens("still {{broken_token}} here")


def test_start_personalizes_queued_messages(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user,
) -> None:
    encryption = TokenEncryptionService()
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    _mark_ready(client, auth_headers, ctx["id"])
    started = client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers)
    assert started.status_code == 200, started.text

    messages = db.query(EmailMessage).filter(EmailMessage.campaign_id == UUID(ctx["id"])).all()
    assert messages
    for message in messages:
        assert "{{" not in (message.subject or "")
        assert "{{" not in (message.rendered_html or "")
        assert message.status == EmailMessageStatus.QUEUED.value
        # Contact company/name or documented fallback applied
        lowered = (message.subject or "").lower()
        assert any(token in lowered for token in ("abc", "arun", "there", "business"))


def test_preview_works_after_recipients_queued(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user,
) -> None:
    encryption = TokenEncryptionService()
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    _mark_ready(client, auth_headers, ctx["id"])
    assert client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers).status_code == 200

    # Recipients are queued, not pending
    assert (
        db.query(CampaignRecipient)
        .filter(
            CampaignRecipient.campaign_id == UUID(ctx["id"]),
            CampaignRecipient.status == CampaignRecipientStatus.QUEUED.value,
        )
        .count()
        >= 1
    )

    preview = client.post(
        f"/api/v1/campaigns/{ctx['id']}/preview",
        headers=auth_headers,
        json={},
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["total_eligible"] >= 1
    assert "{{" not in body["rendered_subject"]
    assert "{{" not in body["rendered_html"]


def test_personalize_queued_endpoint_skips_sent(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user,
) -> None:
    encryption = TokenEncryptionService()
    ctx = _ready_campaign(client, auth_headers, db, admin_user, encryption)
    _mark_ready(client, auth_headers, ctx["id"])
    assert client.post(f"/api/v1/campaigns/{ctx['id']}/start", headers=auth_headers).status_code == 200
    cid = UUID(ctx["id"])
    messages = db.query(EmailMessage).filter(EmailMessage.campaign_id == cid).all()
    sent = messages[0]
    sent.status = EmailMessageStatus.SENT.value
    sent.subject = "ALREADY SENT {{first_name}}"
    sent.rendered_html = "<p>ALREADY SENT {{first_name}}</p>"
    db.commit()

    # Corrupt remaining queued rows to template form
    for message in messages[1:]:
        message.subject = "X {{first_name|there}}"
        message.rendered_html = "<p>{{first_name|there}}</p>"
        message.rendered_text = "{{first_name|there}}"
    db.commit()

    resp = client.post(
        f"/api/v1/campaigns/{ctx['id']}/personalize-queued",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["updated"] >= 1
    db.refresh(sent)
    assert sent.subject == "ALREADY SENT {{first_name}}"


def test_worker_rejects_unresolved_and_duplicate_claim(
    db: Session,
    admin_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import UTC, datetime

    encryption = TokenEncryptionService()
    from tests.test_campaigns import _account, _list_with_contacts, _template
    from app.models.campaign import Campaign
    from app.models.contact import ContactStatus

    account = _account(db, admin_user, encryption)
    contact_list, contacts = _list_with_contacts(
        db,
        admin_user,
        contacts=[
            {
                "email": "claim@example.com",
                "first_name": "Claim",
                "company": "Co",
                "status": ContactStatus.ACTIVE,
            }
        ],
    )
    template = _template(db, admin_user)
    campaign = Campaign(
        user_id=admin_user.id,
        name="Worker claim",
        status=CampaignStatus.RUNNING.value,
        email_account_id=account.id,
        contact_list_id=contact_list.id,
        template_id=template.id,
        snapshot_subject="Hi {{first_name|there}}",
        snapshot_html="<p>{{first_name|there}}</p>",
        snapshot_plain_text="Hi {{first_name|there}}",
        daily_limit=80,
        hourly_limit=15,
        minimum_delay_seconds=0,
        maximum_delay_seconds=0,
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
        subject=campaign.snapshot_subject,
        rendered_html=campaign.snapshot_html,
        rendered_text=campaign.snapshot_plain_text,
        status=EmailMessageStatus.QUEUED.value,
        max_attempts=3,
        next_attempt_at=datetime.now(UTC),
    )
    db.add(message)
    db.commit()

    gmail = MagicMock()
    gmail.send_raw_message.return_value = SendResult(
        provider_message_id="m1",
        provider_thread_id="t1",
    )
    monkeypatch.setattr(
        "app.services.email_account_service.EmailAccountService._get_valid_access_token",
        lambda self, acc: "fake-token",
    )
    worker = CampaignSenderWorker(db, gmail=gmail)
    summary = worker.process_campaign_queue_batch()
    assert summary["claimed"] >= 1
    assert summary["sent"] >= 1
    db.refresh(message)
    assert message.status == EmailMessageStatus.SENT.value
    assert "{{" not in (message.subject or "")

    # Second claim must not re-send
    summary2 = worker.process_campaign_queue_batch()
    assert summary2["sent"] == 0
    assert gmail.send_raw_message.call_count == 1


def test_process_campaign_queue_requires_auth(client: TestClient) -> None:
    assert client.post("/api/v1/system/process-campaign-queue").status_code == 401
