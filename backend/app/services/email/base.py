"""Email provider abstraction for future multi-provider support."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None
    scope: str | list[str] | None
    token_type: str = "Bearer"


@dataclass
class ProviderProfile:
    email_address: str
    display_name: str | None
    provider_account_id: str | None


@dataclass
class ConnectionTestResult:
    connected: bool
    email_address: str | None
    message: str
    error: str | None = None


@dataclass
class SendResult:
    provider_message_id: str | None
    provider_thread_id: str | None
    raw: dict[str, Any] | None = None


class EmailProvider(ABC):
    """Interface implemented by Gmail, Outlook, SMTP, etc."""

    provider_name: str

    @abstractmethod
    def get_authorization_url(self, state: str) -> str:
        ...

    @abstractmethod
    def exchange_code(self, code: str) -> OAuthTokens:
        ...

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> OAuthTokens:
        ...

    @abstractmethod
    def get_profile(self, access_token: str) -> ProviderProfile:
        ...

    @abstractmethod
    def test_connection(self, access_token: str) -> ConnectionTestResult:
        ...

    @abstractmethod
    def send_raw_message(self, access_token: str, raw_mime: bytes) -> SendResult:
        ...

    @abstractmethod
    def revoke_token(self, token: str) -> None:
        ...
