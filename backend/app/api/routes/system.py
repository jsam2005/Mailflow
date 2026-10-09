"""System status routes."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.email_message import EmailMessage, EmailMessageStatus
from app.models.user import User
from app.schemas.system import ProcessCampaignQueueResponse, WorkerHealthResponse
from app.workers import worker_state
from app.workers.campaign_sender_worker import CampaignSenderWorker

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


@router.post("/process-campaign-queue", response_model=ProcessCampaignQueueResponse)
def process_campaign_queue(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProcessCampaignQueueResponse:
    """Hobby-compatible authenticated worker trigger (no Vercel minute cron required)."""
    _ = current_user
    summary = CampaignSenderWorker(db).process_campaign_queue_batch()
    return ProcessCampaignQueueResponse(**summary)
