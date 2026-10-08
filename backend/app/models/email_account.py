"""Email sending account model (Gmail OAuth in Phase 5)."""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class EmailProviderType(str, enum.Enum):
    GMAIL = "gmail"
    OUTLOOK = "outlook"
    SMTP = "smtp"
    SENDGRID = "sendgrid"
    SES = "ses"


class ConnectionStatus(str, enum.Enum):
    CONNECTED = "connected"
    EXPIRED = "expired"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class EmailAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "email_accounts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "provider",
            "email_address",
            name="uq_email_accounts_user_provider_email",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    email_address: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    oauth_access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    oauth_token_expiry: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    oauth_scope: Mapped[Any | None] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=True,
    )

    daily_send_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    hourly_send_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    minimum_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    maximum_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=90)

    sent_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_current_hour: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_daily_reset_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_hourly_reset_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    connection_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ConnectionStatus.DISCONNECTED.value,
        index=True,
    )
    last_connection_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_connection_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    next_send_allowed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[User] = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<EmailAccount id={self.id} provider={self.provider} "
            f"email={self.email_address!r} status={self.connection_status}>"
        )
