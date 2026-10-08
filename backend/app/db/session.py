"""Database engine and session factory."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

settings = get_settings()

_engine_kwargs: dict = {
    "pool_pre_ping": True,
}

# QueuePool options are not valid for SQLite (used in tests).
if settings.database_url.startswith("sqlite"):
    _engine_kwargs.update(
        {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }
    )
else:
    # Serverless-friendly pool: small and recycled; Neon pooler recommended in production.
    pool_size = 1 if settings.environment == "production" else 5
    max_overflow = 1 if settings.environment == "production" else 10
    _engine_kwargs.update(
        {
            "pool_size": pool_size,
            "max_overflow": max_overflow,
            "pool_recycle": 300,
        }
    )

engine = create_engine(settings.database_url, **_engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
