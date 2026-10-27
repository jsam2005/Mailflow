"""Launcher HTTP control-plane security and allowlisting tests."""

from __future__ import annotations

import json
import threading
from http.client import HTTPConnection
from pathlib import Path

import pytest

from launcher.manager import LauncherStatus, ProcessManager
from launcher.server import create_server


class StubManager(ProcessManager):
    def __init__(self, repo_root: Path) -> None:
        super().__init__(
            repo_root,
            browser_opener=lambda _u: None,
            port_checker=lambda _p: False,
            health_checker=lambda _u: False,
            popen=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no spawn")),
        )
        self.starts = 0
        self.stops = 0

    def start(self, *, open_browser: bool = True) -> dict[str, object]:  # noqa: ARG002
        self.starts += 1
        self.status = LauncherStatus.RUNNING
        self.owned = True
        self.error_message = None
        return self.snapshot()

    def stop(self) -> dict[str, object]:
        self.stops += 1
        self.status = LauncherStatus.STOPPED
        self.owned = False
        self.error_message = None
        self._children.clear()
        return self.snapshot()


@pytest.fixture()
def launcher_http(tmp_path: Path):
    (tmp_path / "backend" / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / "frontend" / "node_modules").mkdir(parents=True)
    (tmp_path / ".env").write_text("ENVIRONMENT=development\n", encoding="utf-8")
    mgr = StubManager(tmp_path)
    httpd, state = create_server(
        host="127.0.0.1",
        port=0,
        repo_root=tmp_path,
        manager=mgr,
        token="test-launcher-token-value",
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    port = httpd.server_address[1]
    yield {"port": port, "token": state.token, "manager": mgr}
    httpd.shutdown()
    httpd.server_close()


def _request(
    port: int,
    method: str,
    path: str,
    *,
    token: str | None,
    origin: str | None = "http://127.0.0.1:8765",
) -> tuple[int, dict]:
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    if origin is not None:
        headers["Origin"] = origin
    body = b"{}" if method == "POST" else None
    conn.request(method, path, body=body, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8")
    conn.close()
    data = json.loads(raw) if raw else {}
    return resp.status, data


def test_status_requires_token(launcher_http: dict) -> None:
    port = launcher_http["port"]
    status, data = _request(port, "GET", "/api/status", token=None)
    assert status == 401
    assert data["ok"] is False


def test_start_stop_allowlisted(launcher_http: dict) -> None:
    port = launcher_http["port"]
    token = launcher_http["token"]
    mgr: StubManager = launcher_http["manager"]

    status, data = _request(port, "POST", "/api/start", token=token)
    assert status == 200
    assert data["status"] == "running"
    assert mgr.starts == 1

    status, data = _request(port, "POST", "/api/stop", token=token)
    assert status == 200
    assert data["status"] == "stopped"
    assert mgr.stops == 1


def test_unknown_action_rejected(launcher_http: dict) -> None:
    port = launcher_http["port"]
    token = launcher_http["token"]
    status, data = _request(port, "POST", "/api/exec", token=token)
    assert status == 404
    assert "Allowlisted" in data["error"]


def test_cross_origin_blocked(launcher_http: dict) -> None:
    port = launcher_http["port"]
    token = launcher_http["token"]
    status, data = _request(
        port,
        "POST",
        "/api/stop",
        token=token,
        origin="https://evil.example",
    )
    assert status == 403
    assert "Cross-origin" in data["error"]


def test_frontend_origin_allowed_for_stop(launcher_http: dict) -> None:
    port = launcher_http["port"]
    token = launcher_http["token"]
    status, data = _request(
        port,
        "POST",
        "/api/stop",
        token=token,
        origin="http://127.0.0.1:5173",
    )
    assert status == 200
    assert data["status"] == "stopped"


def test_launcher_html_served(launcher_http: dict) -> None:
    port = launcher_http["port"]
    conn = HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", "/")
    resp = conn.getresponse()
    body = resp.read().decode("utf-8")
    conn.close()
    assert resp.status == 200
    assert "Start MailFlow" in body
    assert "test-launcher-token-value" in body
