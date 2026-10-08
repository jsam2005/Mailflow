"""Contact list model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.user import User


class ContactList(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "contact_lists"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    original_filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_contacts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    user: Mapped[User] = relationship("User", back_populates="contact_lists")
    contacts: Mapped[list[Contact]] = relationship(
        "Contact",
        back_populates="contact_list",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<ContactList id={self.id} name={self.name!r}>"
