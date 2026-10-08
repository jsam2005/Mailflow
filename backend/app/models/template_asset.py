"""Template image asset model."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.email_template import EmailTemplate
    from app.models.user import User


class TemplateAsset(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "template_assets"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("email_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    public_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship("User")
    template: Mapped[EmailTemplate | None] = relationship(
        "EmailTemplate",
        back_populates="assets",
        foreign_keys=[template_id],
    )

    def __repr__(self) -> str:
        return f"<TemplateAsset id={self.id} mime={self.mime_type}>"
