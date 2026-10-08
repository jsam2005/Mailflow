"""Database-backed rate limit buckets."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RateLimitBucket(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "rate_limit_buckets"

    bucket_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
