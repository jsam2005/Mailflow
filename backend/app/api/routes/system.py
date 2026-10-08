"""System status routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.email_message import EmailMessage, EmailMessageStatus
from app.schemas.system import WorkerHealthResponse
from app.workers import worker_state

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/worker-health", response_model=WorkerHealthResponse)
def worker_health(db: Session = Depends(get_db)) -> WorkerHealthResponse:
    settings = get_settings()
    queued = db.scalar(
        select(func.count())
        .select_from(EmailMessage)
        .where(EmailMessage.status == EmailMessageStatus.QUEUED.value)
    ) or 0
    return WorkerHealthResponse(
        scheduler_running=worker_state.scheduler_running,
        campaign_sending_enabled=settings.campaign_sending_enabled,
        last_worker_tick=worker_state.last_worker_tick,
        last_send_success_at=worker_state.last_send_success_at,
        queued_messages=queued,
    )
