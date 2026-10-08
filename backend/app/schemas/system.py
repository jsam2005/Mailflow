"""System health schemas."""

from datetime import datetime

from pydantic import BaseModel


class WorkerHealthResponse(BaseModel):
    scheduler_running: bool
    campaign_sending_enabled: bool
    last_worker_tick: datetime | None = None
    last_send_success_at: datetime | None = None
    queued_messages: int = 0
