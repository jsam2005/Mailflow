"""Local desktop paths and environment.

This module must stay free of settings and database imports. The Windows
entry point calls ``configure_desktop`` before the app package loads
``get_settings()``.
"""

from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

DESKTOP_HOST = "127.0.0.1"
DESKTOP_PORT = 8000

_STORAGE_SUBDIRS = ("imports", "template-images", "attachments")


def desktop_data_root() -> Path:
    """Per-user data directory. Does not live next to the exe."""
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        return Path(local) / "MailFlow"
    return Path.home() / "AppData" / "Local" / "MailFlow"


def sqlite_database_url(db_file: Path) -> str:
    return "sqlite+pysqlite:///" + db_file.resolve().as_posix()


def frontend_dist_dir() -> Path:
    override = os.environ.get("MAILFLOW_FRONTEND_DIST", "").strip()
    if override:
        return Path(override)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "frontend_dist"
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _write_env_file(path: Path, values: dict[str, str]) -> None:
    header = (
        "# MailFlow desktop settings. Safe to edit while the app is stopped.\n"
        "# The database file and storage folder are chosen automatically.\n"
        "# Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET, then start MailFlow again.\n"
    )
    body = "\n".join(f"{key}={value}" for key, value in values.items())
    path.write_text(header + body + "\n", encoding="utf-8")


def _new_fernet_key() -> str:
    from cryptography.fernet import Fernet

    return Fernet.generate_key().decode()


def configure_desktop(data_root: Path | None = None) -> Path:
    """Create the local data folder and export desktop environment variables."""
    root = data_root or desktop_data_root()
    storage = root / "storage"
    root.mkdir(parents=True, exist_ok=True)
    storage.mkdir(parents=True, exist_ok=True)
    for name in _STORAGE_SUBDIRS:
        (storage / name).mkdir(parents=True, exist_ok=True)

    origin = f"http://{DESKTOP_HOST}:{DESKTOP_PORT}"
    env_path = root / "app.env"
    existing = _parse_env_file(env_path)
    if not env_path.is_file():
        existing = {
            "JWT_SECRET": secrets.token_urlsafe(48),
            "TOKEN_ENCRYPTION_KEY": _new_fernet_key(),
            "CRON_SECRET": secrets.token_urlsafe(48),
            "ADMIN_NAME": "Admin",
            "ADMIN_EMAIL": "admin@example.com",
            # Must satisfy PASSWORD_MIN_LENGTH (12). Shown in the console on first run.
            "ADMIN_PASSWORD": secrets.token_urlsafe(15),
            "GOOGLE_CLIENT_ID": "",
            "GOOGLE_CLIENT_SECRET": "",
            "GOOGLE_REDIRECT_URI": f"{origin}/api/v1/email-accounts/google/callback",
            "AUTH_EMAIL_PROVIDER": "console",
            "CAMPAIGN_SENDING_ENABLED": "false",
        }
        _write_env_file(env_path, existing)

    for key, value in existing.items():
        os.environ.setdefault(key, value)

    os.environ.update(
        {
            "MAILFLOW_DESKTOP": "1",
            "ENVIRONMENT": "development",
            "DATABASE_URL": sqlite_database_url(root / "mailflow.db"),
            "STORAGE_PATH": str(storage),
            "STORAGE_PROVIDER": "local",
            "FRONTEND_URL": origin,
            "BACKEND_URL": origin,
            "PROCESS_ROLE": "combined",
            "MAILFLOW_FRONTEND_DIST": str(frontend_dist_dir()),
        }
    )
    return root
