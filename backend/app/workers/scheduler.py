"""APScheduler setup for MailFlow background jobs."""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.core.logging import get_logger
from app.workers.campaign_sender_worker import CampaignSenderWorker
from app.workers import worker_state

logger = get_logger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    settings = get_settings()
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(
        CampaignSenderWorker().tick,
        "interval",
        seconds=settings.campaign_worker_interval_seconds,
        id="campaign_sender",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    worker_state.scheduler_running = True
    logger.info(
        "scheduler.started",
        campaign_worker_interval_seconds=settings.campaign_worker_interval_seconds,
    )
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    worker_state.scheduler_running = False
    logger.info("scheduler.shutdown")
