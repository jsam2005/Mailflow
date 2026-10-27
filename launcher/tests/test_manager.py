"""Focused ProcessManager lifecycle tests (no real uvicorn/vite)."""

from __future__ import annotations

import signal
from pathlib import Path
from types import SimpleNamespace

import pytest

from launcher.manager import LauncherStatus, ProcessManager


class FakeProc:
    def __init__(self, pid: int = 4242) -> None:
        self.pid = pid
        self._code: int | None = None
        self.signals: list[int] = []

    def poll(self) -> int | None:
        return self._code

    def wait(self, timeout: float | None = None) -> int:  # noqa: ARG002
        self._code = self._code if self._code is not None else 0
        return self._code

    def terminate_via_signal(self, sig: int) -> None:
        self.signals.append(sig)
        self._code = 0 if sig in {signal.SIGTERM, signal.SIGKILL} else self._code


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    backend = tmp_path / "backend"
    frontend = tmp_path / "frontend"
    (backend / ".venv" / "bin").mkdir(parents=True)
    (backend / ".venv" / "bin" / "python").write_text("#!/bin/sh\n", encoding="utf-8")
    (backend / ".venv" / "bin" / "python").chmod(0o755)
    (frontend / "node_modules").mkdir(parents=True)
    (tmp_path / ".env").write_text("ENVIRONMENT=development\n", encoding="utf-8")
    return tmp_path


def test_duplicate_start_does_not_spawn_twice(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spawned: list[list[str]] = []
    procs: list[FakeProc] = []

    def fake_popen(cmd, **kwargs):  # noqa: ANN001, ANN003
        proc = FakeProc(pid=1000 + len(procs))
        procs.append(proc)
        spawned.append(list(cmd))
        return proc

    ready = {"n": 0}

    def health(_url: str) -> bool:
        ready["n"] += 1
        return ready["n"] >= 2

    mgr = ProcessManager(
        repo,
        popen=fake_popen,
        sleeper=lambda _s: None,
        port_checker=lambda _p: False,
        health_checker=health,
        browser_opener=lambda _u: None,
        start_timeout_seconds=2,
    )
    monkeypatch.setattr(mgr, "_resolve_npm", lambda: "npm")

    first = mgr.start(open_browser=False)
    assert first["status"] == LauncherStatus.RUNNING.value
    assert len(spawned) == 2

    second = mgr.start(open_browser=False)
    assert second["status"] == LauncherStatus.RUNNING.value
    assert len(spawned) == 2  # no duplicate processes


def test_port_conflict_sets_error(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = ProcessManager(
        repo,
        popen=lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not spawn")),
        sleeper=lambda _s: None,
        port_checker=lambda port: port == 8000,
        health_checker=lambda _u: False,
        browser_opener=lambda _u: None,
    )
    monkeypatch.setattr(mgr, "_resolve_npm", lambda: "npm")
    result = mgr.start(open_browser=False)
    assert result["status"] == LauncherStatus.ERROR.value
    assert "8000" in (result["error"] or "")


def test_failed_startup_aborts_and_cleans(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    procs: list[FakeProc] = []

    def fake_popen(cmd, **kwargs):  # noqa: ANN001, ANN003
        proc = FakeProc(pid=2000 + len(procs))
        procs.append(proc)
        return proc

    killed: list[int] = []

    def fake_killpg(pid: int, sig: int) -> None:
        killed.append(pid)
        for proc in procs:
            if proc.pid == pid:
                proc.terminate_via_signal(sig)

    mgr = ProcessManager(
        repo,
        popen=fake_popen,
        sleeper=lambda _s: None,
        port_checker=lambda _p: False,
        health_checker=lambda _u: False,
        browser_opener=lambda _u: None,
        start_timeout_seconds=0.01,
    )
    monkeypatch.setattr(mgr, "_resolve_npm", lambda: "npm")
    monkeypatch.setattr("launcher.manager.os.killpg", fake_killpg)

    result = mgr.start(open_browser=False)
    assert result["status"] == LauncherStatus.ERROR.value
    assert "Timed out" in (result["error"] or "")
    assert result["owned"] is False
    assert killed  # cleanup attempted


def test_stop_only_owned_processes(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = ProcessManager(
        repo,
        popen=lambda *a, **k: SimpleNamespace(pid=1, poll=lambda: None),
        sleeper=lambda _s: None,
        port_checker=lambda _p: False,
        health_checker=lambda _u: True,
        browser_opener=lambda _u: None,
    )
    # Simulate external already-running services (not owned).
    result = mgr.start(open_browser=False)
    assert result["status"] == LauncherStatus.RUNNING.value
    assert result["owned"] is False

    stopped = mgr.stop()
    assert stopped["status"] == LauncherStatus.RUNNING.value
    assert "Refuse to stop" in (stopped["error"] or "")


def test_missing_venv_fails_clearly(repo: Path) -> None:
    (repo / "backend" / ".venv" / "bin" / "python").unlink()
    mgr = ProcessManager(
        repo,
        browser_opener=lambda _u: None,
        port_checker=lambda _p: False,
        health_checker=lambda _u: False,
    )
    result = mgr.start(open_browser=False)
    assert result["status"] == LauncherStatus.ERROR.value
    assert "virtualenv" in (result["error"] or "").lower()
