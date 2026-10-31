"""Updater unit tests (isolated temp installs; no client/prod databases)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from launcher.manager import LauncherStatus, ProcessManager
from launcher.update_config import should_preserve_relative
from launcher.update_state import UpdateLockError, UpdateStateStore
from launcher.updater import AuthError, MailFlowUpdater, OfflineError


class FakeProc:
    def __init__(self, pid: int = 9) -> None:
        self.pid = pid
        self._code = None

    def poll(self):
        return self._code


@pytest.fixture()
def install(tmp_path: Path) -> Path:
    root = tmp_path / "MailFlow Install"
    (root / "backend").mkdir(parents=True)
    (root / "frontend").mkdir()
    (root / ".env").write_text(
        "DATABASE_URL=postgresql+psycopg2://mailflow:x@localhost:5432/mailflow\n"
        "TOKEN_ENCRYPTION_KEY=test-key-not-used\n"
        "CAMPAIGN_SENDING_ENABLED=false\n",
        encoding="utf-8",
    )
    (root / "storage" / "imports").mkdir(parents=True)
    (root / "storage" / "imports" / "keep.txt").write_text("asset", encoding="utf-8")
    return root


def test_preserve_env_and_storage_paths() -> None:
    assert should_preserve_relative(".env")
    assert should_preserve_relative("backend/.env")
    assert should_preserve_relative("storage/imports/a.csv")
    assert should_preserve_relative("backend/storage/imports/a.csv")
    assert should_preserve_relative(".mailflow/update-state.json")
    assert not should_preserve_relative("backend/app/main.py")
    assert not should_preserve_relative("frontend/src/App.tsx")


def test_update_lock_blocks_concurrent(install: Path) -> None:
    store = UpdateStateStore(install)
    store.acquire()
    with pytest.raises(UpdateLockError):
        store.acquire()
    store.release()
    store.acquire()
    store.release()


def test_check_no_update(install: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = ProcessManager(install, browser_opener=lambda _u: None)
    upd = MailFlowUpdater(install, mgr)
    monkeypatch.setattr(upd, "_resolve_remote_commit", lambda _cfg: "a" * 40)
    monkeypatch.setattr(upd, "_detect_local_commit", lambda: "a" * 40)
    result = upd.check_for_updates()
    assert result.ok
    assert result.update_available is False


def test_check_update_available(install: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = ProcessManager(install, browser_opener=lambda _u: None)
    upd = MailFlowUpdater(install, mgr)
    monkeypatch.setattr(upd, "_resolve_remote_commit", lambda _cfg: "b" * 40)
    monkeypatch.setattr(upd, "_detect_local_commit", lambda: "a" * 40)
    result = upd.check_for_updates()
    assert result.ok
    assert result.update_available is True
    assert result.available_short == "bbbbbbb"


def test_check_offline(install: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = ProcessManager(install, browser_opener=lambda _u: None)
    upd = MailFlowUpdater(install, mgr)

    def boom(_cfg):
        raise OfflineError("offline")

    monkeypatch.setattr(upd, "_resolve_remote_commit", boom)
    result = upd.check_for_updates()
    assert result.ok is False
    assert "reach GitHub" in result.message


def test_check_auth_failure(install: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = ProcessManager(install, browser_opener=lambda _u: None)
    upd = MailFlowUpdater(install, mgr)

    def boom(_cfg):
        raise AuthError("401")

    monkeypatch.setattr(upd, "_resolve_remote_commit", boom)
    result = upd.check_for_updates()
    assert result.ok is False
    assert "authentication" in result.message.lower()


def test_dirty_tree_aborts_update(install: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (install / ".git").mkdir()
    mgr = ProcessManager(install, browser_opener=lambda _u: None)
    upd = MailFlowUpdater(install, mgr)

    def fake_run(cmd, **kwargs):
        if cmd[:3] == ["git", "status", "--porcelain"]:
            return SimpleNamespace(returncode=0, stdout=" M backend/app/main.py\n", stderr="")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(upd, "_run", fake_run)
    result = upd.apply_update(target_commit="c" * 40)
    assert result["ok"] is False
    assert "modifications" in (result.get("error") or "").lower()


def test_failed_backup_keeps_install(install: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = ProcessManager(install, browser_opener=lambda _u: None)
    # Pretend services already stopped
    mgr.status = LauncherStatus.STOPPED
    upd = MailFlowUpdater(install, mgr)

    monkeypatch.setattr(upd, "_assert_not_dirty", lambda: None)
    monkeypatch.setattr(upd, "_prepare_release_dir", lambda cfg, sha: install)
    monkeypatch.setattr(upd, "_build_staged", lambda stage: None)
    monkeypatch.setattr(mgr, "stop", lambda: {"status": "stopped", "owned": False})

    def fail_backup(state):
        raise RuntimeError("Backup failed: could not create a database dump")

    monkeypatch.setattr(upd, "_create_backup", fail_backup)
    synced = {"n": 0}
    monkeypatch.setattr(upd, "_sync_release_into_install", lambda stage: synced.__setitem__("n", 1))

    result = upd.apply_update(target_commit="d" * 40)
    assert result["ok"] is False
    assert "Backup failed" in (result.get("error") or "")
    assert synced["n"] == 0
    assert (install / ".env").is_file()
    assert (install / "storage" / "imports" / "keep.txt").read_text() == "asset"


def test_apply_success_preserves_env(install: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    mgr = ProcessManager(install, browser_opener=lambda _u: None)
    mgr.status = LauncherStatus.STOPPED
    upd = MailFlowUpdater(install, mgr)

    stage = install / ".mailflow" / "releases" / ("e" * 40)
    stage.mkdir(parents=True)
    (stage / "backend" / "app").mkdir(parents=True)
    (stage / "backend" / "app" / "marker.py").write_text("# new\n", encoding="utf-8")
    (stage / "frontend").mkdir()
    (stage / ".env").write_text("SHOULD_NOT_COPY=1\n", encoding="utf-8")

    monkeypatch.setattr(upd, "_assert_not_dirty", lambda: None)
    monkeypatch.setattr(upd, "_prepare_release_dir", lambda cfg, sha: stage)
    monkeypatch.setattr(upd, "_build_staged", lambda s: None)
    monkeypatch.setattr(mgr, "stop", lambda: {"status": "stopped"})
    backup_dir = install / ".mailflow" / "backups" / "t"
    backup_dir.mkdir(parents=True)
    (backup_dir / "mailflow.dump").write_bytes(b"PGDUMPFAKE............")
    monkeypatch.setattr(upd, "_create_backup", lambda state: backup_dir)
    monkeypatch.setattr(upd, "_alembic_current", lambda: "015")
    monkeypatch.setattr(upd, "_run_migrations", lambda s: None)
    monkeypatch.setattr(upd, "_reinstall_runtime_deps", lambda: None)
    monkeypatch.setattr(mgr, "start", lambda open_browser=False: {"status": "running"})

    original_env = (install / ".env").read_text()
    result = upd.apply_update(target_commit="e" * 40)
    assert result["ok"] is True
    assert (install / ".env").read_text() == original_env
    assert "SHOULD_NOT_COPY" not in (install / ".env").read_text()
    assert (install / "backend" / "app" / "marker.py").is_file()
    assert (install / "storage" / "imports" / "keep.txt").read_text() == "asset"


def test_server_update_endpoints(install: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import threading
    from http.client import HTTPConnection

    from launcher.server import create_server
    from launcher.updater import CheckResult

    mgr = ProcessManager(install, browser_opener=lambda _u: None)
    upd = MailFlowUpdater(install, mgr)
    monkeypatch.setattr(
        upd,
        "check_for_updates",
        lambda: CheckResult(
            ok=True,
            update_available=False,
            installed_commit="a" * 40,
            available_commit="a" * 40,
            available_short="aaaaaaa",
            release_ref="main",
            message="up to date",
        ),
    )

    httpd, state = create_server(
        host="127.0.0.1",
        port=0,
        repo_root=install,
        manager=mgr,
        updater=upd,
        token="test-token",
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    try:
        conn = HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(
            "POST",
            "/api/update/check",
            body="{}",
            headers={
                "Authorization": "Bearer test-token",
                "Origin": "http://127.0.0.1:8765",
                "Content-Type": "application/json",
            },
        )
        resp = conn.getresponse()
        raw = resp.read().decode()
        conn.close()
        assert resp.status == 200
        data = json.loads(raw)
        assert data["ok"] is True
        assert data["update_available"] is False
    finally:
        httpd.shutdown()
        httpd.server_close()
