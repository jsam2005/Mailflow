"""Production hardening tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_recipient import CampaignRecipient, CampaignRecipientStatus
from app.models.contact import ContactStatus
from app.models.email_message import EmailMessage, EmailMessageStatus
from app.models.user import User
from app.services.suppression_service import SuppressionService
from app.services.token_encryption_service import TokenEncryptionService
from app.services.unsubscribe_service import UnsubscribeService
from app.workers.campaign_sender_worker import CampaignSenderWorker
from tests.test_campaigns import _account, _list_with_contacts, _template


PROD_ENV = {
    "ENVIRONMENT": "production",
    "DATABASE_URL": "postgresql+psycopg2://u:p@db.example.com/mailflow",
    "JWT_SECRET": "x" * 40,
    "TOKEN_ENCRYPTION_KEY": "I_1WmUSBsquzW12HDIFVXjBnygdlDdlF82xrmaualtU=",
    "GOOGLE_CLIENT_ID": "id",
    "GOOGLE_CLIENT_SECRET": "secret",
    "GOOGLE_REDIRECT_URI": "https://example.com/api/v1/email-accounts/google/callback",
    "FRONTEND_URL": "https://example.com",
    "CRON_SECRET": "c" * 40,
    "ENABLE_LOCAL_SCHEDULER": "false",
    "STORAGE_PROVIDER": "local",
    "CAMPAIGN_SENDING_ENABLED": "false",
}


def _apply_env(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def test_production_config_disables_scheduler(monkeypatch: pytest.MonkeyPatch) -> None:
    _apply_env(monkeypatch, PROD_ENV)
    settings = Settings()
    assert settings.is_production
    assert settings.local_scheduler_enabled is False
    get_settings.cache_clear()


def test_production_rejects_localhost_db(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {**PROD_ENV, "DATABASE_URL": "postgresql+psycopg2://u:p@localhost/mailflow"}
    _apply_env(monkeypatch, env)
    with pytest.raises(ValueError, match="localhost"):
        Settings()
    get_settings.cache_clear()


def test_production_requires_https_oauth(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {
        **PROD_ENV,
        "GOOGLE_REDIRECT_URI": "http://localhost:8000/api/v1/email-accounts/google/callback",
    }
    _apply_env(monkeypatch, env)
    with pytest.raises(ValueError, match="GOOGLE_REDIRECT_URI"):
        Settings()
    get_settings.cache_clear()


def test_cron_requires_secret(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "cron-secret-value-at-least-32-chars-long"
    monkeypatch.setenv("CRON_SECRET", secret)
    get_settings.cache_clear()

    assert client.post("/api/v1/internal/workers/campaign-send").status_code == 401
    assert (
        client.post(
            "/api/v1/internal/workers/campaign-send",
            headers={"Authorization": "Bearer wrong"},
        ).status_code
        == 401
    )
    ok = client.get(
        "/api/v1/internal/workers/campaign-send",
        headers={"Authorization": f"Bearer {secret}"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert "claimed" in body
    assert "sent" in body
    assert "execution_ms" in body
    get_settings.cache_clear()


def test_health_exposes_safe_fields(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert "environment" in data
    blob = str(data).lower()
    assert "secret" not in blob
    assert "password" not in blob
    assert "token_encryption" not in blob


def test_unsubscribe_tamper_rejected(client: TestClient) -> None:
    bad = client.get("/api/v1/public/unsubscribe/not-a-real-token")
    assert bad.status_code == 422
    bad_post = client.post("/api/v1/public/unsubscribe/not-a-real-token")
    assert bad_post.status_code == 422


def test_unsubscribe_and_suppression(
    client: TestClient,
    db: Session,
    admin_user: User,
) -> None:
    token = UnsubscribeService(db).make_token(
        user_id=admin_user.id,
        email="leave@example.com",
    )
    preview = client.get(f"/api/v1/public/unsubscribe/{token}")
    assert preview.status_code == 200
    assert preview.json()["status"] == "pending_confirmation"
    assert not SuppressionService(db).is_suppressed(admin_user.id, "leave@example.com")

    ok = client.post(f"/api/v1/public/unsubscribe/{token}")
    assert ok.status_code == 200
    assert ok.json()["status"] == "unsubscribed"
    assert SuppressionService(db).is_suppressed(admin_user.id, "leave@example.com")


def test_suppression_cancels_queued_mail(
    db: Session,
    admin_user: User,
) -> None:
    encryption = TokenEncryptionService()
    account = _account(db, admin_user, encryption, email="send@gmail.com")
    cl, contacts = _list_with_contacts(
        db,
        admin_user,
        contacts=[
            {
                "email": "leave2@example.com",
                "first_name": "L",
                "status": ContactStatus.ACTIVE,
            },
        ],
    )
    template = _template(db, admin_user)
    contact = contacts[0]
    campaign = Campaign(
        user_id=admin_user.id,
        name="U",
        status=CampaignStatus.RUNNING.value,
        email_account_id=account.id,
        template_id=template.id,
        contact_list_id=cl.id,
        snapshot_subject="Hi",
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
        to_email="leave2@example.com",
        subject="Hi",
        rendered_html="<p>Hi</p>",
        status=EmailMessageStatus.QUEUED.value,
        next_attempt_at=datetime.now(UTC),
    )
    db.add(message)
    db.commit()

    SuppressionService(db).suppress(
        admin_user,
        "leave2@example.com",
        reason="manual",
        source="test",
    )
    db.refresh(message)
    assert message.status == EmailMessageStatus.CANCELLED.value


def test_worker_batch_summary(db: Session) -> None:
    summary = CampaignSenderWorker(db).process_campaign_queue_batch()
    assert "claimed" in summary
    assert "execution_ms" in summary
    assert summary["claimed"] <= get_settings().campaign_worker_batch_size


def test_cors_origins_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    _apply_env(
        monkeypatch,
        {
            **PROD_ENV,
            "CORS_ORIGINS": "https://app.example.com",
            "FRONTEND_URL": "https://app.example.com",
        },
    )
    settings = Settings()
    assert settings.cors_origin_list == ["https://app.example.com"]
    assert "*" not in settings.cors_origin_list
    get_settings.cache_clear()


def test_no_default_admin_in_production_bootstrap() -> None:
    """Production path must not auto-create admin from empty credentials."""
    from app.main import lifespan
    import inspect

    source = inspect.getsource(lifespan)
    assert "ensure_admin_user" in source
    assert "is_development" in source
    assert "is_production" in source
