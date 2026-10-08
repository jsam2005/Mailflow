"""Health check endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    database: str | None = None
    version: str | None = None
    environment: str | None = None
    storage_provider: str | None = None
    scheduler_mode: str | None = None


@router.get("/health", response_model=HealthResponse)
def liveness() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get("/api/v1/health", response_model=HealthResponse)
def readiness(db: Session = Depends(get_db)) -> HealthResponse:
    settings = get_settings()
    db.execute(text("SELECT 1"))
    return HealthResponse(
        status="ok",
        database="ok",
        version=settings.app_version,
        environment=settings.environment,
        storage_provider=settings.storage_provider,
        scheduler_mode=(
            "local_apscheduler" if settings.local_scheduler_enabled else "serverless_cron"
        ),
    )
