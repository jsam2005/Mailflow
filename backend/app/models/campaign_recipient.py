"""Frozen campaign audience snapshot."""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.contact import Contact
    from app.models.email_message import EmailMessage


class CampaignRecipientStatus(str, enum.Enum):
    PENDING = "pending"
    EXCLUDED = "excluded"
    INVALID = "invalid"
    SUPPRESSED = "suppressed"
    # Reserved for Phase 7+
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REPLIED = "replied"
    UNSUBSCRIBED = "unsubscribed"


class CampaignRecipient(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaign_recipients"
    __table_args__ = (
        UniqueConstraint(
            "campaign_id",
            "contact_id",
            name="uq_campaign_recipients_campaign_contact",
        ),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CampaignRecipientStatus.PENDING.value,
        index=True,
    )
    exclusion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    campaign: Mapped[Campaign] = relationship("Campaign", back_populates="recipients")
    contact: Mapped[Contact] = relationship("Contact")
    email_message: Mapped[EmailMessage | None] = relationship(
        "EmailMessage",
        back_populates="campaign_recipient",
        uselist=False,
    )

    def __repr__(self) -> str:
        return (
            f"<CampaignRecipient id={self.id} campaign={self.campaign_id} "
            f"status={self.status}>"
        )
