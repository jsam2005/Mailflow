"""Windows desktop entry. Sets local SQLite paths before the app imports settings."""

from __future__ import annotations

import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path


def _ensure_backend_on_path() -> None:
    if getattr(sys, "frozen", False):
        return
    backend = Path(__file__).resolve().parents[2] / "backend"
    backend_str = str(backend)
    if backend.is_dir() and backend_str not in sys.path:
        sys.path.insert(0, backend_str)


def _open_when_ready(url: str) -> None:
    health = url.rstrip("/") + "/health"
    for _ in range(50):
        try:
            with urllib.request.urlopen(health, timeout=0.5) as response:
                if response.status == 200:
                    webbrowser.open(url.rstrip("/") + "/")
                    return
        except Exception:
            time.sleep(0.2)


def _already_running(url: str) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=1) as response:
            return response.status == 200
    except Exception:
        return False


def main() -> None:
    _ensure_backend_on_path()
    from app.desktop_runtime import DESKTOP_HOST, DESKTOP_PORT, configure_desktop

    running_origin = f"http://{DESKTOP_HOST}:{DESKTOP_PORT}"
    if _already_running(running_origin):
        print(f"MailFlow is already running at {running_origin}/ - opening it.")
        webbrowser.open(running_origin + "/")
        time.sleep(2)
        return

    from app.desktop_runtime import desktop_data_root

    first_run = not (desktop_data_root() / "mailflow.db").is_file()
    root = configure_desktop()
    # Settings read ".env" from the working directory; keep it inside the data folder.
    import os

    os.chdir(root)
    origin = f"http://{DESKTOP_HOST}:{DESKTOP_PORT}"
    print(f"MailFlow data: {root}")
    print(f"Database: {root / 'mailflow.db'}")
    print(f"Settings: {root / 'app.env'}")
    print(f"Open {origin}/")
    if first_run:
        print("")
        print("First run: sign in with")
        print(f"  Email:    {os.environ.get('ADMIN_EMAIL', '')}")
        print(f"  Password: {os.environ.get('ADMIN_PASSWORD', '')}")
        print("(Also saved in app.env in the data folder.)")
        print("")
    print("Leave this window open. Close it to stop MailFlow.")

    threading.Thread(target=_open_when_ready, args=(origin,), daemon=True).start()

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=DESKTOP_HOST,
        port=DESKTOP_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
