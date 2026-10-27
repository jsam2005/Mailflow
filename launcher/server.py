"""Loopback-only MailFlow launcher control service.

Serves launcher.html and fixed allowlisted start/stop/open/status actions.
Never accepts arbitrary shell commands from the browser.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from launcher.manager import ProcessManager

LAUNCHER_HOST = "127.0.0.1"
LAUNCHER_PORT = 8765
STATIC_DIR = Path(__file__).resolve().parent / "static"
REPO_ROOT = Path(__file__).resolve().parent.parent

ALLOWED_ORIGINS = frozenset(
    {
        f"http://{LAUNCHER_HOST}:{LAUNCHER_PORT}",
        f"http://localhost:{LAUNCHER_PORT}",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    }
)


class LauncherState:
    def __init__(self, manager: ProcessManager, token: str) -> None:
        self.manager = manager
        self.token = token
        self._action_lock = threading.Lock()


def _json_bytes(payload: dict[str, Any], status: int = 200) -> tuple[int, bytes, str]:
    body = json.dumps(payload).encode("utf-8")
    return status, body, "application/json; charset=utf-8"


def make_handler(state: LauncherState) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: object) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

        def _client_is_loopback(self) -> bool:
            host = self.client_address[0]
            return host in {"127.0.0.1", "::1", "localhost"}

        def _origin(self) -> str | None:
            origin = self.headers.get("Origin")
            if origin:
                return origin.rstrip("/")
            referer = self.headers.get("Referer")
            if not referer:
                return None
            parsed = urlparse(referer)
            if not parsed.scheme or not parsed.netloc:
                return None
            return f"{parsed.scheme}://{parsed.netloc}"

        def _cors_headers(self) -> dict[str, str]:
            origin = self._origin()
            headers: dict[str, str] = {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            }
            if origin in ALLOWED_ORIGINS:
                headers["Access-Control-Allow-Origin"] = origin
                headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
                headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
                headers["Vary"] = "Origin"
            return headers

        def _send(
            self,
            status: int,
            body: bytes,
            content_type: str,
            extra: dict[str, str] | None = None,
        ) -> None:
            self.send_response(status)
            headers = self._cors_headers()
            headers["Content-Type"] = content_type
            headers["Content-Length"] = str(len(body))
            if extra:
                headers.update(extra)
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _reject(self, status: int, message: str) -> None:
            status_code, body, ctype = _json_bytes({"ok": False, "error": message}, status)
            self._send(status_code, body, ctype)

        def _authorize_control(self) -> bool:
            if not self._client_is_loopback():
                self._reject(403, "Launcher controls are loopback-only.")
                return False
            origin = self._origin()
            # Same-origin launcher UI may omit Origin on some GETs; mutating
            # routes still require the session token below.
            if origin is not None and origin not in ALLOWED_ORIGINS:
                self._reject(403, "Cross-origin request blocked.")
                return False
            auth = self.headers.get("Authorization", "")
            expected = f"Bearer {state.token}"
            if not secrets.compare_digest(auth, expected):
                self._reject(401, "Missing or invalid launcher token.")
                return False
            return True

        def do_OPTIONS(self) -> None:  # noqa: N802
            if not self._client_is_loopback():
                self._reject(403, "Launcher controls are loopback-only.")
                return
            self._send(204, b"", "text/plain")

        def do_GET(self) -> None:  # noqa: N802
            if not self._client_is_loopback():
                self._reject(403, "Launcher controls are loopback-only.")
                return
            path = urlparse(self.path).path
            if path in {"/", "/launcher.html"}:
                self._serve_static("launcher.html", inject_token=True)
                return
            if path == "/stopped" or path == "/stopped.html":
                self._serve_static("stopped.html", inject_token=True)
                return
            if path == "/api/status":
                # Status is readable with token to avoid leaking process info.
                if not self._authorize_control():
                    return
                payload = {"ok": True, **state.manager.snapshot()}
                status, body, ctype = _json_bytes(payload)
                self._send(status, body, ctype)
                return
            self._reject(404, "Not found.")

        def do_POST(self) -> None:  # noqa: N802
            if not self._authorize_control():
                return
            path = urlparse(self.path).path
            length = int(self.headers.get("Content-Length") or 0)
            if length > 4096:
                self._reject(413, "Request body too large.")
                return
            if length:
                self.rfile.read(length)

            if path == "/api/start":
                with state._action_lock:
                    result = state.manager.start(open_browser=True)
                status, body, ctype = _json_bytes({"ok": result.get("status") != "error", **result})
                self._send(status, body, ctype)
                return
            if path == "/api/stop":
                with state._action_lock:
                    result = state.manager.stop()
                ok = result.get("status") == "stopped"
                status, body, ctype = _json_bytes({"ok": ok, **result})
                self._send(status, body, ctype)
                return
            if path == "/api/open":
                try:
                    with state._action_lock:
                        result = state.manager.open_app()
                    status, body, ctype = _json_bytes({"ok": True, **result})
                    self._send(status, body, ctype)
                except RuntimeError as exc:
                    self._reject(409, str(exc))
                return
            self._reject(404, "Unknown action. Allowlisted: /api/start, /api/stop, /api/open.")

        def _serve_static(self, name: str, *, inject_token: bool) -> None:
            target = (STATIC_DIR / name).resolve()
            if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
                self._reject(404, "Not found.")
                return
            text = target.read_text(encoding="utf-8")
            if inject_token:
                text = text.replace("__LAUNCHER_TOKEN__", state.token)
                text = text.replace(
                    "__LAUNCHER_ORIGIN__",
                    f"http://{LAUNCHER_HOST}:{LAUNCHER_PORT}",
                )
            body = text.encode("utf-8")
            self._send(200, body, "text/html; charset=utf-8")

    return Handler


def create_server(
    *,
    host: str = LAUNCHER_HOST,
    port: int = LAUNCHER_PORT,
    repo_root: Path | None = None,
    manager: ProcessManager | None = None,
    token: str | None = None,
) -> tuple[ThreadingHTTPServer, LauncherState]:
    root = repo_root or REPO_ROOT
    session_token = token or secrets.token_urlsafe(32)
    # Child Vite process reads these for the in-app Exit button.
    import os

    os.environ["MAILFLOW_LAUNCHER_TOKEN"] = session_token
    os.environ["MAILFLOW_LAUNCHER_URL"] = f"http://{host}:{port}"

    mgr = manager or ProcessManager(root)
    state = LauncherState(mgr, session_token)
    httpd = ThreadingHTTPServer((host, port), make_handler(state))
    return httpd, state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MailFlow local launcher service")
    parser.add_argument("--host", default=LAUNCHER_HOST)
    parser.add_argument("--port", type=int, default=LAUNCHER_PORT)
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open launcher UI in the default browser",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args(argv)

    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print("Refusing to bind launcher outside loopback.", file=sys.stderr)
        return 2

    try:
        httpd, state = create_server(host=args.host, port=args.port, repo_root=args.repo_root)
    except OSError as exc:
        print(f"Could not start launcher on {args.host}:{args.port}: {exc}", file=sys.stderr)
        return 1

    url = f"http://{args.host}:{args.port}/"
    print(f"MailFlow launcher listening on {url}")
    print("Keep this window open while using the launcher.")
    if args.open:
        state.manager._open_browser(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down launcher…")
    finally:
        try:
            state.manager.stop()
        except Exception:  # noqa: BLE001
            pass
        httpd.server_close()
    return 0


if __name__ == "__main__":
    # Allow `python launcher/server.py` without installed package.
    if __package__ is None:
        sys.path.insert(0, str(REPO_ROOT))
        from launcher.server import main as _main

        raise SystemExit(_main())
    raise SystemExit(main())
