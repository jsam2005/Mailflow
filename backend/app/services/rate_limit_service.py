"""Simple database-backed rate limiting for auth-sensitive endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import RateLimitError
from app.models.rate_limit import RateLimitBucket


class RateLimitService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def check_and_hit(self, key: str, *, limit: int, window_seconds: int = 60) -> None:
        now = datetime.now(UTC)
        window_start = now - timedelta(seconds=window_seconds)
        row = self.db.scalar(
            select(RateLimitBucket)
            .where(
                RateLimitBucket.bucket_key == key,
                RateLimitBucket.window_started_at >= window_start,
            )
            .order_by(RateLimitBucket.window_started_at.desc())
        )
        if row is None:
            row = RateLimitBucket(
                bucket_key=key,
                window_started_at=now,
                hit_count=1,
            )
            self.db.add(row)
            self.db.commit()
            return
        if row.hit_count >= limit:
            raise RateLimitError("Too many requests. Please try again shortly.")
        row.hit_count += 1
        self.db.commit()

    def cleanup(self, older_than_seconds: int = 3600) -> None:
        cutoff = datetime.now(UTC) - timedelta(seconds=older_than_seconds)
        self.db.execute(
            delete(RateLimitBucket).where(RateLimitBucket.window_started_at < cutoff)
        )
        self.db.commit()
