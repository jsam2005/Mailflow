"""Email provider and message building utilities."""

from app.services.email.base import EmailProvider
from app.services.email.email_message_builder import EmailMessageBuilder
from app.services.email.gmail_provider import GMAIL_SCOPES, GmailProvider

__all__ = [
    "EmailProvider",
    "EmailMessageBuilder",
    "GmailProvider",
    "GMAIL_SCOPES",
]
