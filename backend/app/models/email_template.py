"""Email template model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.template_asset import TemplateAsset
    from app.models.user import User


class EmailTemplate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "email_templates"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    plain_text_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    plain_text_customized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped[User] = relationship("User")
    assets: Mapped[list[TemplateAsset]] = relationship(
        "TemplateAsset",
        back_populates="template",
        foreign_keys="TemplateAsset.template_id",
    )

    def __repr__(self) -> str:
        return f"<EmailTemplate id={self.id} name={self.name!r}>"
