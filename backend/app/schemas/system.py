"""System health schemas."""

from datetime import datetime

from pydantic import BaseModel


class WorkerHealthResponse(BaseModel):
    scheduler_running: bool
    campaign_sending_enabled: bool
    test_allowlist_configured: bool = False
    test_allowlist_size: int = 0
    last_worker_tick: datetime | None = None
    last_send_success_at: datetime | None = None
    queued_messages: int = 0


class ProcessCampaignQueueResponse(BaseModel):
    claimed: int
    sent: int
    failed: int
    deferred: int
    cancelled: int
    completed_campaigns: int
    sending_enabled: bool
    execution_ms: int


class PersonalizeQueuedResponse(BaseModel):
    updated: int
    failed: int
    total_queued: int
