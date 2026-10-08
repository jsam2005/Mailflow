"""Campaign planning model (sending starts in Phase 7)."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.campaign_recipient import CampaignRecipient
    from app.models.contact_list import ContactList
    from app.models.email_account import EmailAccount
    from app.models.email_template import EmailTemplate
    from app.models.user import User


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    READY = "ready"
    CANCELLED = "cancelled"
    # Reserved for Phase 7+
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaigns"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=CampaignStatus.DRAFT.value,
        index=True,
    )

    email_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True,
    )
    contact_list_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contact_lists.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Campaign-specific edits (do not mutate original template)
    subject_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    html_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    plain_text_override: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Frozen content when status → ready (immune to later template edits)
    snapshot_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snapshot_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_plain_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    daily_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hourly_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    minimum_delay_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maximum_delay_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    stop_on_reply: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    skip_suppressed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[User] = relationship("User")
    email_account: Mapped[EmailAccount | None] = relationship("EmailAccount")
    template: Mapped[EmailTemplate | None] = relationship("EmailTemplate")
    contact_list: Mapped[ContactList | None] = relationship("ContactList")
    recipients: Mapped[list[CampaignRecipient]] = relationship(
        "CampaignRecipient",
        back_populates="campaign",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} name={self.name!r} status={self.status}>"
