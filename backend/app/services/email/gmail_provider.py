"""Gmail OAuth 2.0 and Gmail API send provider."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import OAuthError, ValidationAppError
from app.core.logging import get_logger
from app.services.email.base import (
    ConnectionTestResult,
    EmailProvider,
    OAuthTokens,
    ProviderProfile,
    SendResult,
)

logger = get_logger(__name__)

# Least-privilege scopes for identify + send test email (no mailbox read).
GMAIL_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.send",
]

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_PROFILE_URL = "https://gmail.googleapis.com/gmail/v1/users/me/profile"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class GmailProvider(EmailProvider):
    provider_name = "gmail"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = http_client

    def _require_oauth_config(self) -> None:
        if not self.settings.google_client_id or not self.settings.google_client_secret:
            raise OAuthError(
                "Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."
            )

    def _client_ctx(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=30.0)

    def get_authorization_url(self, state: str) -> str:
        self._require_oauth_config()
        params = {
            "client_id": self.settings.google_client_id,
            "redirect_uri": self.settings.google_redirect_uri,
            "response_type": "code",
            "scope": " ".join(GMAIL_SCOPES),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
        }
        return f"{AUTH_URL}?{urlencode(params)}"

    def exchange_code(self, code: str) -> OAuthTokens:
        self._require_oauth_config()
        if not code:
            raise OAuthError("Missing authorization code.")
        client = self._client_ctx()
        close = self._client is None
        try:
            response = client.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "redirect_uri": self.settings.google_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        finally:
            if close:
                client.close()
        return self._parse_token_response(response, require_refresh=True)

    def refresh_access_token(self, refresh_token: str) -> OAuthTokens:
        self._require_oauth_config()
        if not refresh_token:
            raise OAuthError("Missing refresh token. Reconnect Gmail.")
        client = self._client_ctx()
        close = self._client is None
        try:
            response = client.post(
                TOKEN_URL,
                data={
                    "client_id": self.settings.google_client_id,
                    "client_secret": self.settings.google_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
        finally:
            if close:
                client.close()
        tokens = self._parse_token_response(response, require_refresh=False)
        if not tokens.refresh_token:
            tokens.refresh_token = refresh_token
        return tokens

    def get_profile(self, access_token: str) -> ProviderProfile:
        client = self._client_ctx()
        close = self._client is None
        try:
            response = client.get(
                USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        finally:
            if close:
                client.close()
        if response.status_code >= 400:
            raise OAuthError("Could not retrieve Google account profile.")
        data = response.json()
        email = data.get("email")
        if not email:
            raise OAuthError("Google did not return an email address for this account.")
        return ProviderProfile(
            email_address=email.lower().strip(),
            display_name=data.get("name"),
            provider_account_id=data.get("id"),
        )

    def test_connection(self, access_token: str) -> ConnectionTestResult:
        client = self._client_ctx()
        close = self._client is None
        try:
            response = client.get(
                GMAIL_PROFILE_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        finally:
            if close:
                client.close()
        if response.status_code == 401:
            return ConnectionTestResult(
                connected=False,
                email_address=None,
                message="Google authorization has expired. Reconnect this account.",
                error="unauthorized",
            )
        if response.status_code == 403:
            return ConnectionTestResult(
                connected=False,
                email_address=None,
                message="Gmail API access is insufficient. Reconnect and grant send permission.",
                error="insufficient_scope",
            )
        if response.status_code >= 400:
            return ConnectionTestResult(
                connected=False,
                email_address=None,
                message="Gmail API is temporarily unavailable. Try again shortly.",
                error="api_error",
            )
        data = response.json()
        email = data.get("emailAddress")
        return ConnectionTestResult(
            connected=True,
            email_address=email,
            message="Gmail connection is working.",
        )

    def send_raw_message(self, access_token: str, raw_mime: bytes) -> SendResult:
        encoded = base64.urlsafe_b64encode(raw_mime).decode("ascii").rstrip("=")
        client = self._client_ctx()
        close = self._client is None
        try:
            response = client.post(
                GMAIL_SEND_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"raw": encoded},
            )
        finally:
            if close:
                client.close()
        if response.status_code == 401:
            raise OAuthError(
                "Google authorization has expired. Reconnect this account."
            )
        if response.status_code == 403:
            raise OAuthError(
                "Insufficient Gmail send permission. Reconnect this account."
            )
        if response.status_code >= 400:
            logger.warning(
                "gmail.send_failed",
                status_code=response.status_code,
            )
            raise ValidationAppError("Gmail could not send the test email. Try again.")
        data = response.json()
        return SendResult(
            provider_message_id=data.get("id"),
            provider_thread_id=data.get("threadId"),
            raw={"id": data.get("id"), "threadId": data.get("threadId")},
        )

    def revoke_token(self, token: str) -> None:
        if not token:
            return
        client = self._client_ctx()
        close = self._client is None
        try:
            client.post(REVOKE_URL, params={"token": token})
        except httpx.HTTPError:
            logger.warning("gmail.revoke_failed")
        finally:
            if close:
                client.close()

    def _parse_token_response(
        self,
        response: httpx.Response,
        *,
        require_refresh: bool,
    ) -> OAuthTokens:
        if response.status_code >= 400:
            logger.warning("gmail.token_exchange_failed", status_code=response.status_code)
            raise OAuthError("Could not complete Google authorization. Please try again.")
        data = response.json()
        access_token = data.get("access_token")
        if not access_token:
            raise OAuthError("Google did not return an access token.")
        refresh_token = data.get("refresh_token")
        if require_refresh and not refresh_token:
            raise OAuthError(
                "Google did not return a refresh token. Remove MailFlow access in "
                "Google Account permissions and reconnect."
            )
        expires_in = data.get("expires_in")
        expires_at = None
        if expires_in is not None:
            expires_at = datetime.now(UTC) + timedelta(seconds=int(expires_in))
        return OAuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            scope=data.get("scope"),
            token_type=data.get("token_type", "Bearer"),
        )
