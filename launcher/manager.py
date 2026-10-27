"""Own and lifecycle-manage local MailFlow backend/frontend processes.

Only stops processes this manager started. Never uses killall, taskkill
without a PID, or other broad name-based kills.

Campaign worker (in-process APScheduler under PROCESS_ROLE=combined) shuts
down via uvicorn graceful stop → FastAPI lifespan → shutdown_scheduler.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse


class LauncherStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ServiceSpec:
    name: str
    port: int
    cwd: Path
    command: list[str]
    env: dict[str, str] = field(default_factory=dict)
    ready_url: str | None = None


@dataclass
class ManagedProcess:
    name: str
    port: int
    process: subprocess.Popen[bytes]
    command: list[str]


class PortOccupiedError(RuntimeError):
    def __init__(self, port: int, message: str) -> None:
        super().__init__(message)
        self.port = port


def venv_python(backend_dir: Path) -> Path:
    """Return the project venv interpreter path for the current OS."""
    if sys.platform == "win32":
        return backend_dir / ".venv" / "Scripts" / "python.exe"
    return backend_dir / ".venv" / "bin" / "python"


def setup_hint() -> str:
    if sys.platform == "win32":
        return "Run Setup-MailFlow-Windows.cmd once"
    return "Run launcher/setup.command once"


class ProcessManager:
    """Start/stop MailFlow services with duplicate-start protection."""

    def __init__(
        self,
        repo_root: Path,
        *,
        frontend_url: str = "http://127.0.0.1:5173",
        backend_health_url: str = "http://127.0.0.1:8000/api/v1/health",
        frontend_port: int = 5173,
        backend_port: int = 8000,
        start_timeout_seconds: float = 90.0,
        stop_grace_seconds: float = 30.0,
        popen: Callable[..., subprocess.Popen[bytes]] | None = None,
        sleeper: Callable[[float], None] | None = None,
        port_checker: Callable[[int], bool] | None = None,
        health_checker: Callable[[str], bool] | None = None,
        browser_opener: Callable[[str], None] | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.frontend_url = frontend_url.rstrip("/")
        self.backend_health_url = backend_health_url
        self.frontend_port = frontend_port
        self.backend_port = backend_port
        self.start_timeout_seconds = start_timeout_seconds
        self.stop_grace_seconds = stop_grace_seconds
        self._popen = popen or subprocess.Popen
        self._sleep = sleeper or time.sleep
        self._port_in_use = port_checker or self._default_port_in_use
        self._url_ready = health_checker or self._default_url_ready
        self._open_browser = browser_opener or self._default_open_browser

        self._lock = threading.RLock()
        self.status = LauncherStatus.STOPPED
        self.error_message: str | None = None
        self.notice: str | None = None
        self.owned: bool = False
        self._children: dict[str, ManagedProcess] = {}
        self._start_generation = 0

    @property
    def backend_dir(self) -> Path:
        return self.repo_root / "backend"

    @property
    def frontend_dir(self) -> Path:
        return self.repo_root / "frontend"

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "status": self.status.value,
                "error": self.error_message,
                "notice": self.notice,
                "owned": self.owned,
                "frontend_url": self.frontend_url,
                "backend_port": self.backend_port,
                "frontend_port": self.frontend_port,
                "services": {
                    name: {
                        "pid": child.process.pid,
                        "port": child.port,
                        "alive": child.process.poll() is None,
                    }
                    for name, child in self._children.items()
                },
            }

    def start(self, *, open_browser: bool = True) -> dict[str, object]:
        with self._lock:
            if self.status in {LauncherStatus.STARTING, LauncherStatus.STOPPING}:
                return self.snapshot()
            if self.status == LauncherStatus.RUNNING and self._children_alive():
                if open_browser:
                    self._open_browser(self.frontend_url)
                return self.snapshot()

            # External instance already healthy — do not spawn duplicates.
            if self._services_appear_ready() and not self._children:
                self.status = LauncherStatus.RUNNING
                self.owned = False
                self.error_message = None
                self.notice = (
                    "MailFlow appears to already be running on the expected ports, "
                    "but it was not started by this launcher. Open works; Stop will "
                    "not kill those processes."
                )
                if open_browser:
                    self._open_browser(self.frontend_url)
                return self.snapshot()

            self._start_generation += 1
            generation = self._start_generation
            self.status = LauncherStatus.STARTING
            self.error_message = None
            self.notice = None
            self.owned = True

        try:
            self._validate_prerequisites()
            specs = self._build_specs()
            self._ensure_ports_free(specs)
            for spec in specs:
                self._spawn(spec)
            self._wait_until_ready(generation)
            with self._lock:
                if generation != self._start_generation:
                    return self.snapshot()
                self.status = LauncherStatus.RUNNING
                self.error_message = None
            if open_browser:
                self._open_browser(self.frontend_url)
        except Exception as exc:  # noqa: BLE001 — surface as launcher error state
            self._abort_start(str(exc))
        return self.snapshot()

    def stop(self) -> dict[str, object]:
        with self._lock:
            if self.status == LauncherStatus.STOPPING:
                return self.snapshot()
            if self.status == LauncherStatus.STOPPED and not self._children:
                return self.snapshot()
            if not self.owned or not self._children:
                self.error_message = (
                    "Refuse to stop: no launcher-owned processes. "
                    "Only services started by this launcher can be stopped."
                )
                if self.status == LauncherStatus.RUNNING and not self.owned:
                    return self.snapshot()
                self.status = LauncherStatus.ERROR
                return self.snapshot()
            self.status = LauncherStatus.STOPPING
            self.error_message = None
            self.notice = None
            children = list(self._children.values())

        errors: list[str] = []
        for child in sorted(children, key=lambda c: 0 if c.name == "frontend" else 1):
            try:
                self._terminate_owned(child)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{child.name}: {exc}")

        with self._lock:
            self._children.clear()
            self.owned = False
            if errors:
                self.status = LauncherStatus.ERROR
                self.error_message = "; ".join(errors)
            else:
                self.status = LauncherStatus.STOPPED
                self.error_message = None
        return self.snapshot()

    def open_app(self) -> dict[str, object]:
        with self._lock:
            snap = self.snapshot()
        if snap["status"] != LauncherStatus.RUNNING.value:
            raise RuntimeError("MailFlow is not running yet. Click Start first.")
        self._open_browser(self.frontend_url)
        return self.snapshot()

    def _children_alive(self) -> bool:
        return any(child.process.poll() is None for child in self._children.values())

    def _validate_prerequisites(self) -> None:
        python = venv_python(self.backend_dir)
        if not python.is_file():
            raise RuntimeError(
                f"Backend virtualenv missing. {setup_hint()} "
                f"(expected {python})."
            )
        if not (self.frontend_dir / "node_modules").is_dir():
            raise RuntimeError(
                f"Frontend dependencies missing. {setup_hint()} (npm install)."
            )
        env_file = self.backend_dir / ".env"
        root_env = self.repo_root / ".env"
        if not env_file.is_file() and not root_env.is_file():
            raise RuntimeError(
                f"No .env found. {setup_hint()} to create local configuration."
            )

    def _build_specs(self) -> list[ServiceSpec]:
        python = str(venv_python(self.backend_dir))
        npm = self._resolve_npm()
        launcher_token = os.environ.get("MAILFLOW_LAUNCHER_TOKEN", "")
        launcher_url = os.environ.get(
            "MAILFLOW_LAUNCHER_URL", "http://127.0.0.1:8765"
        )

        backend_env = {
            **os.environ,
            "PROCESS_ROLE": os.environ.get("PROCESS_ROLE", "combined"),
        }
        frontend_env = {
            **os.environ,
            "VITE_LOCAL_LAUNCHER_URL": launcher_url,
            "VITE_LOCAL_LAUNCHER_TOKEN": launcher_token,
        }

        # On Windows, prefer npm.cmd via shell-less list form with resolved path.
        frontend_cmd = [
            npm,
            "run",
            "dev",
            "--",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.frontend_port),
        ]

        return [
            ServiceSpec(
                name="backend",
                port=self.backend_port,
                cwd=self.backend_dir,
                command=[
                    python,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(self.backend_port),
                ],
                env=backend_env,
                ready_url=self.backend_health_url,
            ),
            ServiceSpec(
                name="frontend",
                port=self.frontend_port,
                cwd=self.frontend_dir,
                command=frontend_cmd,
                env=frontend_env,
                ready_url=self.frontend_url + "/",
            ),
        ]

    def _resolve_npm(self) -> str:
        if sys.platform == "win32":
            for name in ("npm.cmd", "npm.exe", "npm"):
                found = self._which(name)
                if found:
                    return found
            return "npm.cmd"
        for candidate in ("/opt/homebrew/bin/npm", "/usr/local/bin/npm"):
            if Path(candidate).is_file():
                return candidate
        return self._which("npm") or "npm"

    @staticmethod
    def _which(name: str) -> str | None:
        from shutil import which

        return which(name)

    def _ensure_ports_free(self, specs: list[ServiceSpec]) -> None:
        for spec in specs:
            if self._port_in_use(spec.port):
                owned = self._children.get(spec.name)
                if owned and owned.process.poll() is None:
                    continue
                raise PortOccupiedError(
                    spec.port,
                    f"Port {spec.port} is already in use. Stop the other process "
                    f"or use Open if MailFlow is already running.",
                )

    def _spawn_kwargs(self) -> dict:
        if sys.platform == "win32":
            # New process group so we can signal only this tree later.
            return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        return {"start_new_session": True}

    def _spawn(self, spec: ServiceSpec) -> None:
        log_dir = self.repo_root / "launcher" / ".runtime"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{spec.name}.log"
        log_file = open(log_path, "ab", buffering=0)  # noqa: SIM115
        try:
            proc = self._popen(
                spec.command,
                cwd=str(spec.cwd),
                env=spec.env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                **self._spawn_kwargs(),
            )
        except OSError as exc:
            log_file.close()
            raise RuntimeError(f"Failed to start {spec.name}: {exc}") from exc

        with self._lock:
            self._children[spec.name] = ManagedProcess(
                name=spec.name,
                port=spec.port,
                process=proc,
                command=spec.command,
            )
        log_file.close()

    def _wait_until_ready(self, generation: int) -> None:
        deadline = time.monotonic() + self.start_timeout_seconds
        while time.monotonic() < deadline:
            with self._lock:
                if generation != self._start_generation:
                    return
                if self.status == LauncherStatus.STOPPING:
                    raise RuntimeError("Start cancelled because stop was requested.")
                for name, child in self._children.items():
                    code = child.process.poll()
                    if code is not None:
                        raise RuntimeError(
                            f"{name} exited early with code {code}. "
                            f"See launcher/.runtime/{name}.log"
                        )
            if self._services_appear_ready():
                return
            self._sleep(0.4)
        raise RuntimeError(
            "Timed out waiting for MailFlow to become ready. "
            "Check launcher/.runtime/*.log and that Postgres is running."
        )

    def _services_appear_ready(self) -> bool:
        return self._url_ready(self.backend_health_url) and self._url_ready(
            self.frontend_url + "/"
        )

    def _abort_start(self, message: str) -> None:
        with self._lock:
            children = list(self._children.values())
            self._children.clear()
        for child in children:
            try:
                self._terminate_owned(child)
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            self.owned = False
            self.status = LauncherStatus.ERROR
            self.error_message = message
            self.notice = None

    def _terminate_owned(self, child: ManagedProcess) -> None:
        proc = child.process
        if proc.poll() is not None:
            return

        if sys.platform == "win32":
            self._terminate_windows_tree(proc.pid)
        else:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                return
            except PermissionError as exc:
                raise RuntimeError(
                    f"No permission to signal {child.name} pid {proc.pid}"
                ) from exc

        deadline = time.monotonic() + self.stop_grace_seconds
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                return
            self._sleep(0.2)

        if sys.platform == "win32":
            self._terminate_windows_tree(proc.pid, force=True)
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    @staticmethod
    def _terminate_windows_tree(pid: int, *, force: bool = False) -> None:
        """Stop only the given PID and its descendants (not all python/node)."""
        args = ["taskkill", "/PID", str(pid), "/T"]
        if force:
            args.append("/F")
        try:
            subprocess.run(  # noqa: S603
                args,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass

    @staticmethod
    def _default_port_in_use(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex(("127.0.0.1", port)) == 0

    @staticmethod
    def _default_url_ready(url: str) -> bool:
        try:
            parsed = urlparse(url)
            if parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
                return False
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:  # noqa: S310
                return 200 <= getattr(resp, "status", 200) < 500
        except (urllib.error.URLError, TimeoutError, OSError):
            return False

    @staticmethod
    def _default_open_browser(url: str) -> None:
        try:
            webbrowser.open(url)
        except Exception:  # noqa: BLE001
            if sys.platform == "darwin":
                try:
                    subprocess.Popen(  # noqa: S603
                        ["open", url],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except OSError:
                    pass
            elif sys.platform == "win32":
                try:
                    os.startfile(url)  # type: ignore[attr-defined]
                except OSError:
                    pass


def write_runtime_token(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"token": token}), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
