"""Contact model."""

from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.contact_list import ContactList


class ContactStatus(str, enum.Enum):
    ACTIVE = "active"
    INVALID = "invalid"
    UNSUBSCRIBED = "unsubscribed"
    BOUNCED = "bounced"
    SUPPRESSED = "suppressed"


class Contact(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contacts"
    __table_args__ = (
        UniqueConstraint(
            "contact_list_id",
            "normalized_email",
            name="uq_contacts_list_normalized_email",
        ),
    )

    contact_list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contact_lists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[ContactStatus] = mapped_column(
        Enum(
            ContactStatus,
            name="contact_status",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            native_enum=False,
            length=32,
        ),
        nullable=False,
        default=ContactStatus.ACTIVE,
        index=True,
    )
    # Attribute cannot be named `metadata` (reserved by SQLAlchemy DeclarativeBase).
    contact_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB(), "postgresql"),
        nullable=False,
        default=dict,
    )

    contact_list: Mapped[ContactList] = relationship(
        "ContactList",
        back_populates="contacts",
    )

    def __repr__(self) -> str:
        return f"<Contact id={self.id} email={self.email!r}>"
