"""Global per-user email suppression list."""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class SuppressionReason(str, enum.Enum):
    UNSUBSCRIBE = "unsubscribe"
    BOUNCE = "bounce"
    COMPLAINT = "complaint"
    MANUAL = "manual"


class SuppressionList(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "suppression_list"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_email", name="uq_suppression_user_email"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped[User] = relationship("User")
