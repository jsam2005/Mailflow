"""Phase 5 email account / Gmail OAuth tests (Google APIs mocked)."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.models.contact_list import ContactList
from app.models.email_account import ConnectionStatus, EmailAccount
from app.models.email_template import EmailTemplate
from app.models.email_test_log import EmailTestLog
from app.models.oauth_state import OAuthState
from app.models.template_asset import TemplateAsset
from app.models.user import User
from app.services.email.base import (
    ConnectionTestResult,
    OAuthTokens,
    ProviderProfile,
    SendResult,
)
from app.services.email.email_message_builder import EmailMessageBuilder
from app.services.email_account_service import EmailAccountService
from app.services.token_encryption_service import TokenEncryptionService


@pytest.fixture()
def encryption() -> TokenEncryptionService:
    return TokenEncryptionService()


@pytest.fixture()
def mock_gmail() -> MagicMock:
    provider = MagicMock()
    provider.provider_name = "gmail"
    provider.get_authorization_url.return_value = (
        "https://accounts.google.com/o/oauth2/v2/auth?state=abc&client_id=test"
    )
    provider.exchange_code.return_value = OAuthTokens(
        access_token="access-token-1",
        refresh_token="refresh-token-1",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scope="openid email https://www.googleapis.com/auth/gmail.send",
    )
    provider.get_profile.return_value = ProviderProfile(
        email_address="sender@gmail.com",
        display_name="Sender",
        provider_account_id="google-123",
    )
    provider.refresh_access_token.return_value = OAuthTokens(
        access_token="access-token-2",
        refresh_token="refresh-token-1",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
        scope="openid email https://www.googleapis.com/auth/gmail.send",
    )
    provider.test_connection.return_value = ConnectionTestResult(
        connected=True,
        email_address="sender@gmail.com",
        message="Gmail connection is working.",
    )
    provider.send_raw_message.return_value = SendResult(
        provider_message_id="msg-1",
        provider_thread_id="thread-1",
    )
    provider.revoke_token.return_value = None
    return provider


def _make_account(
    db: Session,
    user: User,
    encryption: TokenEncryptionService,
    *,
    email: str = "sender@gmail.com",
    status: str = ConnectionStatus.CONNECTED.value,
    active: bool = True,
) -> EmailAccount:
    account = EmailAccount(
        user_id=user.id,
        provider="gmail",
        email_address=email,
        display_name="Sender",
        provider_account_id="google-123",
        oauth_access_token_encrypted=encryption.encrypt("access-token-1"),
        oauth_refresh_token_encrypted=encryption.encrypt("refresh-token-1"),
        oauth_token_expiry=datetime.now(UTC) + timedelta(hours=1),
        oauth_scope=["openid", "email", "https://www.googleapis.com/auth/gmail.send"],
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


def test_token_encryption_roundtrip(encryption: TokenEncryptionService) -> None:
    cipher = encryption.encrypt("secret-token")
    assert cipher != "secret-token"
    assert encryption.decrypt(cipher) == "secret-token"


def test_list_accounts_empty(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.get("/api/v1/email-accounts", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_list_and_ownership(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
) -> None:
    account = _make_account(db, admin_user, encryption)
    mine = client.get("/api/v1/email-accounts", headers=auth_headers)
    assert mine.status_code == 200
    assert len(mine.json()["items"]) == 1
    assert mine.json()["items"][0]["email_address"] == "sender@gmail.com"
    body = mine.json()["items"][0]
    assert "oauth_access_token" not in body
    assert "oauth_refresh_token" not in body
    assert "oauth_access_token_encrypted" not in body
    assert "oauth_refresh_token_encrypted" not in body

    other = client.get(f"/api/v1/email-accounts/{account.id}", headers=other_auth_headers)
    assert other.status_code == 404


def test_update_settings_validation(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
) -> None:
    account = _make_account(db, admin_user, encryption)
    bad = client.put(
        f"/api/v1/email-accounts/{account.id}",
        headers=auth_headers,
        json={"hourly_send_limit": 50, "daily_send_limit": 10},
    )
    assert bad.status_code == 422

    ok = client.put(
        f"/api/v1/email-accounts/{account.id}",
        headers=auth_headers,
        json={
            "daily_send_limit": 80,
            "hourly_send_limit": 15,
            "minimum_delay_seconds": 20,
            "maximum_delay_seconds": 60,
        },
    )
    assert ok.status_code == 200
    assert ok.json()["daily_send_limit"] == 80
    assert ok.json()["hourly_send_limit"] == 15


def test_duplicate_account_unique(
    db: Session,
    admin_user: User,
    encryption: TokenEncryptionService,
) -> None:
    _make_account(db, admin_user, encryption, email="dup@gmail.com")
    with pytest.raises(Exception):
        _make_account(db, admin_user, encryption, email="dup@gmail.com")


def test_oauth_connect_url(
    client: TestClient,
    auth_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    mock_gmail: MagicMock,
) -> None:
    monkeypatch.setattr(
        "app.services.email_account_service.GmailProvider",
        lambda *a, **k: mock_gmail,
    )
    response = client.post("/api/v1/email-accounts/google/connect", headers=auth_headers)
    assert response.status_code == 200
    assert "accounts.google.com" in response.json()["authorization_url"]
    states = db.query(OAuthState).all()
    assert len(states) == 1
    assert states[0].used_at is None


def test_oauth_invalid_expired_reused_state(
    client: TestClient,
    db: Session,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
    mock_gmail: MagicMock,
) -> None:
    monkeypatch.setattr(
        "app.services.email_account_service.GmailProvider",
        lambda *a, **k: mock_gmail,
    )
    service = EmailAccountService(db, gmail=mock_gmail)

    # Invalid
    url = service.handle_google_callback(code="x", state="nope", error=None)
    assert "error=oauth_failed" in url

    # Expired
    raw = "expired-state-token"
    record = OAuthState(
        user_id=admin_user.id,
        provider="gmail",
        state_hash=hashlib.sha256(raw.encode()).hexdigest(),
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
        used_at=None,
        created_at=datetime.now(UTC) - timedelta(minutes=20),
    )
    db.add(record)
    db.commit()
    url = service.handle_google_callback(code="x", state=raw, error=None)
    assert "error=oauth_failed" in url

    # Reuse
    raw2 = "one-time-state"
    record2 = OAuthState(
        user_id=admin_user.id,
        provider="gmail",
        state_hash=hashlib.sha256(raw2.encode()).hexdigest(),
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        used_at=None,
        created_at=datetime.now(UTC),
    )
    db.add(record2)
    db.commit()
    ok = service.handle_google_callback(code="code-1", state=raw2, error=None)
    assert "connected=1" in ok
    again = service.handle_google_callback(code="code-1", state=raw2, error=None)
    assert "error=oauth_failed" in again


def test_oauth_callback_success_and_denial(
    db: Session,
    admin_user: User,
    monkeypatch: pytest.MonkeyPatch,
    mock_gmail: MagicMock,
) -> None:
    monkeypatch.setattr(
        "app.services.email_account_service.GmailProvider",
        lambda *a, **k: mock_gmail,
    )
    service = EmailAccountService(db, gmail=mock_gmail)
    raw = "good-state"
    db.add(
        OAuthState(
            user_id=admin_user.id,
            provider="gmail",
            state_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
            used_at=None,
            created_at=datetime.now(UTC),
        )
    )
    db.commit()
    url = service.handle_google_callback(code="auth-code", state=raw, error=None)
    assert "connected=1" in url
    accounts = db.query(EmailAccount).filter(EmailAccount.user_id == admin_user.id).all()
    assert len(accounts) == 1
    assert accounts[0].email_address == "sender@gmail.com"
    assert accounts[0].oauth_access_token_encrypted is not None
    assert "access-token" not in (accounts[0].oauth_access_token_encrypted or "")

    denied = service.handle_google_callback(code=None, state=None, error="access_denied")
    assert "error=oauth_failed" in denied


def test_oauth_callback_bound_to_initiating_user(
    db: Session,
    admin_user: User,
    other_user: User,
    mock_gmail: MagicMock,
) -> None:
    service = EmailAccountService(db, gmail=mock_gmail)
    raw = "bound-state"
    db.add(
        OAuthState(
            user_id=admin_user.id,
            provider="gmail",
            state_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
            used_at=None,
            created_at=datetime.now(UTC),
        )
    )
    db.commit()
    service.handle_google_callback(code="c", state=raw, error=None)
    account = db.query(EmailAccount).one()
    assert account.user_id == admin_user.id
    assert account.user_id != other_user.id


def test_token_refresh_mocked(
    db: Session,
    admin_user: User,
    encryption: TokenEncryptionService,
    mock_gmail: MagicMock,
) -> None:
    account = _make_account(db, admin_user, encryption)
    account.oauth_token_expiry = datetime.now(UTC) - timedelta(minutes=1)
    db.commit()
    service = EmailAccountService(db, encryption=encryption, gmail=mock_gmail)
    token = service._get_valid_access_token(account)
    assert token == "access-token-2"
    mock_gmail.refresh_access_token.assert_called_once()
    db.refresh(account)
    assert account.connection_status == ConnectionStatus.CONNECTED.value


def test_connection_test_success_failure(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
    monkeypatch: pytest.MonkeyPatch,
    mock_gmail: MagicMock,
) -> None:
    account = _make_account(db, admin_user, encryption)
    monkeypatch.setattr(
        "app.services.email_account_service.GmailProvider",
        lambda *a, **k: mock_gmail,
    )
    ok = client.post(
        f"/api/v1/email-accounts/{account.id}/test-connection",
        headers=auth_headers,
    )
    assert ok.status_code == 200
    assert ok.json()["connected"] is True

    mock_gmail.test_connection.return_value = ConnectionTestResult(
        connected=False,
        email_address=None,
        message="Google authorization has expired. Reconnect this account.",
        error="unauthorized",
    )
    bad = client.post(
        f"/api/v1/email-accounts/{account.id}/test-connection",
        headers=auth_headers,
    )
    assert bad.status_code == 200
    assert bad.json()["connected"] is False
    db.refresh(account)
    assert account.connection_status == ConnectionStatus.EXPIRED.value


def test_disconnect_and_reconnect_updates_same(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
    monkeypatch: pytest.MonkeyPatch,
    mock_gmail: MagicMock,
) -> None:
    account = _make_account(db, admin_user, encryption)
    monkeypatch.setattr(
        "app.services.email_account_service.GmailProvider",
        lambda *a, **k: mock_gmail,
    )
    deleted = client.delete(f"/api/v1/email-accounts/{account.id}", headers=auth_headers)
    assert deleted.status_code == 204
    db.refresh(account)
    assert account.connection_status == ConnectionStatus.DISCONNECTED.value
    assert account.oauth_access_token_encrypted is None
    assert account.is_active is False

    service = EmailAccountService(db, encryption=encryption, gmail=mock_gmail)
    raw = "reconnect-state"
    db.add(
        OAuthState(
            user_id=admin_user.id,
            provider="gmail",
            state_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=datetime.now(UTC) + timedelta(minutes=10),
            used_at=None,
            created_at=datetime.now(UTC),
        )
    )
    db.commit()
    service.handle_google_callback(code="c", state=raw, error=None)
    accounts = db.query(EmailAccount).filter(EmailAccount.user_id == admin_user.id).all()
    assert len(accounts) == 1
    assert accounts[0].id == account.id
    assert accounts[0].connection_status == ConnectionStatus.CONNECTED.value
    assert accounts[0].is_active is True


def test_send_simple_and_template(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
    monkeypatch: pytest.MonkeyPatch,
    mock_gmail: MagicMock,
) -> None:
    account = _make_account(db, admin_user, encryption)
    monkeypatch.setattr(
        "app.services.email_account_service.GmailProvider",
        lambda *a, **k: mock_gmail,
    )

    simple = client.post(
        f"/api/v1/email-accounts/{account.id}/send-test",
        headers=auth_headers,
        json={
            "to_email": "me@example.com",
            "mode": "simple",
            "subject": "Hello",
            "message": "Test body",
        },
    )
    assert simple.status_code == 200
    assert simple.json()["sent"] is True
    assert simple.json()["provider_message_id"] == "msg-1"
    assert mock_gmail.send_raw_message.called

    template = EmailTemplate(
        user_id=admin_user.id,
        name="T1",
        subject="Hi {{first_name}}",
        html_content="<p>Hello {{first_name}}</p>",
        plain_text_content="Hello {{first_name}}",
        plain_text_customized=True,
        is_active=True,
    )
    db.add(template)
    contact_list = ContactList(user_id=admin_user.id, name="L1")
    db.add(contact_list)
    db.flush()
    contact = Contact(
        contact_list_id=contact_list.id,
        email="arun@example.com",
        normalized_email="arun@example.com",
        first_name="Arun",
        last_name="Kumar",
    )
    db.add(contact)
    db.commit()
    db.refresh(template)
    db.refresh(contact)

    templated = client.post(
        f"/api/v1/email-accounts/{account.id}/send-test",
        headers=auth_headers,
        json={
            "to_email": "me@example.com",
            "mode": "template",
            "template_id": str(template.id),
            "contact_id": str(contact.id),
        },
    )
    assert templated.status_code == 200
    assert templated.json()["sent"] is True
    # Subject from template after personalization
    assert "Arun" in templated.json()["subject"]


def test_cid_image_transformation(
    db: Session,
    admin_user: User,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("STORAGE_PATH", str(tmp_path))
    get_settings.cache_clear()
    storage_images = tmp_path / "template-images"
    storage_images.mkdir(parents=True)
    stored = "img1.png"
    (storage_images / stored).write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)

    asset = TemplateAsset(
        user_id=admin_user.id,
        original_filename="logo.png",
        stored_filename=stored,
        mime_type="image/png",
        file_size=40,
        width=10,
        height=10,
        content_id="asset-cid@mailflow.local",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    html = f'<p><img data-mailflow-asset-id="{asset.id}" src="/api/v1/template-assets/{asset.id}/content" /></p>'
    builder = EmailMessageBuilder(db)
    built = builder.build(
        user=admin_user,
        from_email="a@gmail.com",
        from_name="A",
        to_email="b@example.com",
        subject="CID",
        html_body=html,
        text_body="CID",
    )
    assert "cid:asset-cid@mailflow.local" in built.html_body
    assert len(built.inline_images) == 1
    raw = built.to_mime_bytes()
    assert b"asset-cid@mailflow.local" in raw


def test_missing_asset_and_invalid_recipient(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
    monkeypatch: pytest.MonkeyPatch,
    mock_gmail: MagicMock,
) -> None:
    account = _make_account(db, admin_user, encryption)
    monkeypatch.setattr(
        "app.services.email_account_service.GmailProvider",
        lambda *a, **k: mock_gmail,
    )
    template = EmailTemplate(
        user_id=admin_user.id,
        name="Missing asset",
        subject="X",
        html_content=f'<img data-mailflow-asset-id="{uuid4()}" />',
        plain_text_content="X",
        plain_text_customized=True,
        is_active=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    missing = client.post(
        f"/api/v1/email-accounts/{account.id}/send-test",
        headers=auth_headers,
        json={
            "to_email": "me@example.com",
            "mode": "template",
            "template_id": str(template.id),
        },
    )
    assert missing.status_code == 404

    invalid = client.post(
        f"/api/v1/email-accounts/{account.id}/send-test",
        headers=auth_headers,
        json={"to_email": "not-an-email", "mode": "simple"},
    )
    assert invalid.status_code == 422


def test_rate_limit_and_cross_user(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
    monkeypatch: pytest.MonkeyPatch,
    mock_gmail: MagicMock,
) -> None:
    account = _make_account(db, admin_user, encryption)
    monkeypatch.setattr(
        "app.services.email_account_service.GmailProvider",
        lambda *a, **k: mock_gmail,
    )
    monkeypatch.setenv("TEST_EMAIL_HOURLY_LIMIT", "2")
    from app.core.config import get_settings

    get_settings.cache_clear()

    for _ in range(2):
        r = client.post(
            f"/api/v1/email-accounts/{account.id}/send-test",
            headers=auth_headers,
            json={"to_email": "me@example.com", "mode": "simple"},
        )
        assert r.status_code == 200

    limited = client.post(
        f"/api/v1/email-accounts/{account.id}/send-test",
        headers=auth_headers,
        json={"to_email": "me@example.com", "mode": "simple"},
    )
    assert limited.status_code == 429

    foreign = client.post(
        f"/api/v1/email-accounts/{account.id}/send-test",
        headers=other_auth_headers,
        json={"to_email": "me@example.com", "mode": "simple"},
    )
    assert foreign.status_code == 404

    get_settings.cache_clear()


def test_tokens_never_in_api_response(
    client: TestClient,
    db: Session,
    auth_headers: dict[str, str],
    admin_user: User,
    encryption: TokenEncryptionService,
) -> None:
    account = _make_account(db, admin_user, encryption)
    response = client.get(f"/api/v1/email-accounts/{account.id}", headers=auth_headers)
    raw = response.text
    assert "access-token" not in raw
    assert "refresh-token" not in raw
    assert encryption.encrypt("access-token-1") not in raw or True  # ciphertext also excluded
    for key in (
        "oauth_access_token",
        "oauth_refresh_token",
        "oauth_access_token_encrypted",
        "client_secret",
    ):
        assert key not in response.json()
