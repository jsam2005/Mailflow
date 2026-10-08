"""Internal cron / worker endpoints (not for browsers)."""

from __future__ import annotations

import hmac
import time

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.logging import get_logger
from app.db.session import get_db
from app.workers.campaign_sender_worker import CampaignSenderWorker

router = APIRouter(prefix="/api/v1/internal/workers", tags=["internal"])
logger = get_logger(__name__)


class CampaignSendBatchResponse(BaseModel):
    claimed: int
    sent: int
    failed: int
    deferred: int
    cancelled: int
    completed_campaigns: int
    sending_enabled: bool
    execution_ms: int


def require_cron_secret(
    authorization: str | None = Header(default=None),
) -> None:
    settings = get_settings()
    expected = settings.cron_secret
    if not expected:
        raise UnauthorizedError("Cron authentication is not configured.")
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Invalid cron credentials.")
    provided = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(provided, expected):
        raise UnauthorizedError("Invalid cron credentials.")


def _run_batch(db: Session) -> CampaignSendBatchResponse:
    started = time.perf_counter()
    summary = CampaignSenderWorker(db).process_campaign_queue_batch()
    logger.info(
        "cron.campaign_send",
        claimed=summary.get("claimed"),
        sent=summary.get("sent"),
        failed=summary.get("failed"),
        deferred=summary.get("deferred"),
        execution_ms=int((time.perf_counter() - started) * 1000),
    )
    return CampaignSendBatchResponse(**summary)


@router.post("/campaign-send", response_model=CampaignSendBatchResponse)
def campaign_send_batch_post(
    db: Session = Depends(get_db),
    _: None = Depends(require_cron_secret),
) -> CampaignSendBatchResponse:
    return _run_batch(db)


@router.get("/campaign-send", response_model=CampaignSendBatchResponse)
def campaign_send_batch_get(
    db: Session = Depends(get_db),
    _: None = Depends(require_cron_secret),
) -> CampaignSendBatchResponse:
    """Vercel Cron invokes GET; Authorization: Bearer $CRON_SECRET is attached automatically."""
    return _run_batch(db)
