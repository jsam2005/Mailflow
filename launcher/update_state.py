"""Persistent update operation state and exclusive lock."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from launcher.update_config import ensure_mailflow_dirs, mailflow_dir


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass
class UpdateOperationState:
    phase: str = "idle"
    message: str = ""
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    target_commit: str | None = None
    target_short: str | None = None
    previous_commit: str | None = None
    backup_path: str | None = None
    migration_revision_before: str | None = None
    lock_pid: int | None = None
    progress: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class UpdateLockError(RuntimeError):
    pass


class UpdateStateStore:
    def __init__(self, install_root: Path) -> None:
        self.install_root = install_root.resolve()
        ensure_mailflow_dirs(self.install_root)
        self.state_path = mailflow_dir(self.install_root) / "update-state.json"
        self.lock_path = mailflow_dir(self.install_root) / "update.lock"

    def read(self) -> UpdateOperationState:
        if not self.state_path.is_file():
            return UpdateOperationState()
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return UpdateOperationState(phase="failed", error="Corrupt update-state.json")
        return UpdateOperationState(
            phase=str(data.get("phase") or "idle"),
            message=str(data.get("message") or ""),
            error=data.get("error"),
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
            target_commit=data.get("target_commit"),
            target_short=data.get("target_short"),
            previous_commit=data.get("previous_commit"),
            backup_path=data.get("backup_path"),
            migration_revision_before=data.get("migration_revision_before"),
            lock_pid=data.get("lock_pid"),
            progress=list(data.get("progress") or []),
        )

    def write(self, state: UpdateOperationState) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state.to_dict(), indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.state_path)

    def append_progress(self, state: UpdateOperationState, line: str) -> UpdateOperationState:
        state.progress = [*state.progress, f"{_now()} {line}"][-80:]
        state.message = line
        self.write(state)
        return state

    def acquire(self) -> UpdateOperationState:
        """Exclusive lock via O_EXCL create. Refuses if another live update holds it."""
        if self.lock_path.exists():
            try:
                raw = self.lock_path.read_text(encoding="utf-8").strip()
                old_pid = int(raw.split()[0])
            except (OSError, ValueError):
                old_pid = -1
            if old_pid > 0 and _pid_alive(old_pid):
                raise UpdateLockError(
                    f"An update is already running (pid {old_pid}). "
                    "Wait for it to finish or remove .mailflow/update.lock only if that process is dead."
                )
            try:
                self.lock_path.unlink()
            except OSError as exc:
                raise UpdateLockError(f"Could not clear stale update lock: {exc}") from exc

        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(str(self.lock_path), flags, 0o600)
        except FileExistsError as exc:
            raise UpdateLockError("Could not acquire update lock (concurrent click).") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(f"{os.getpid()} {_now()}\n")

        state = UpdateOperationState(
            phase="starting",
            message="Update lock acquired",
            started_at=_now(),
            lock_pid=os.getpid(),
            progress=[f"{_now()} Update lock acquired"],
        )
        self.write(state)
        return state

    def release(self) -> None:
        try:
            if self.lock_path.is_file():
                raw = self.lock_path.read_text(encoding="utf-8").strip()
                pid = int(raw.split()[0])
                if pid == os.getpid():
                    self.lock_path.unlink()
        except (OSError, ValueError):
            pass

    def is_busy(self) -> bool:
        state = self.read()
        if state.phase in {
            "idle",
            "success",
            "failed",
            "no_update",
            "checked",
        }:
            if self.lock_path.exists():
                try:
                    pid = int(self.lock_path.read_text(encoding="utf-8").split()[0])
                    return _pid_alive(pid)
                except (OSError, ValueError):
                    return False
            return False
        if self.lock_path.exists():
            try:
                pid = int(self.lock_path.read_text(encoding="utf-8").split()[0])
                return _pid_alive(pid)
            except (OSError, ValueError):
                return True
        return state.phase not in {"idle", "success", "failed", "no_update", "checked"}


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def sleep_brief(seconds: float = 0.05) -> None:
    time.sleep(seconds)
