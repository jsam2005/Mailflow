"""Outbound campaign email message (one per campaign recipient)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.campaign_recipient import CampaignRecipient
    from app.models.contact import Contact
    from app.models.email_account import EmailAccount
    from app.models.user import User


class EmailMessageStatus(str, enum.Enum):
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EmailMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "email_messages"
    __table_args__ = (
        UniqueConstraint(
            "campaign_recipient_id",
            name="uq_email_messages_campaign_recipient",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaign_recipients.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email_account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    to_email: Mapped[str] = mapped_column(String(320), nullable=False)
    to_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_html: Mapped[str] = mapped_column(Text, nullable=False)
    rendered_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EmailMessageStatus.QUEUED.value,
        index=True,
    )
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rfc_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship("User")
    campaign: Mapped[Campaign] = relationship("Campaign")
    campaign_recipient: Mapped[CampaignRecipient] = relationship("CampaignRecipient")
    contact: Mapped[Contact] = relationship("Contact")
    email_account: Mapped[EmailAccount] = relationship("EmailAccount")

    def __repr__(self) -> str:
        return f"<EmailMessage id={self.id} status={self.status} to={self.to_email!r}>"
