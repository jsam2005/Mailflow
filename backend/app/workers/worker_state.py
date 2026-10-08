"""In-process worker health metrics."""

from __future__ import annotations

from datetime import datetime

scheduler_running: bool = False
last_worker_tick: datetime | None = None
last_send_success_at: datetime | None = None
