"""Trusted update source configuration for local MailFlow installs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_OWNER = "jsam2005"
DEFAULT_REPO = "Mailflow"
DEFAULT_REF = "main"
DEFAULT_REMOTE = "https://github.com/jsam2005/Mailflow.git"

MAILFLOW_DIRNAME = ".mailflow"


@dataclass
class UpdateConfig:
    github_owner: str = DEFAULT_OWNER
    github_repo: str = DEFAULT_REPO
    release_ref: str = DEFAULT_REF
    remote_url: str = DEFAULT_REMOTE

    @property
    def api_repo(self) -> str:
        return f"{self.github_owner}/{self.github_repo}"

    @property
    def zipball_url_for(self) -> str:
        # Caller appends /{sha}
        return f"https://github.com/{self.github_owner}/{self.github_repo}/archive"


def mailflow_dir(install_root: Path) -> Path:
    return install_root / MAILFLOW_DIRNAME


def config_path(install_root: Path) -> Path:
    return mailflow_dir(install_root) / "update-config.json"


def installed_path(install_root: Path) -> Path:
    return mailflow_dir(install_root) / "installed.json"


def ensure_mailflow_dirs(install_root: Path) -> Path:
    root = mailflow_dir(install_root)
    (root / "releases").mkdir(parents=True, exist_ok=True)
    (root / "backups").mkdir(parents=True, exist_ok=True)
    return root


def load_update_config(install_root: Path) -> UpdateConfig:
    ensure_mailflow_dirs(install_root)
    path = config_path(install_root)
    if not path.is_file():
        cfg = UpdateConfig()
        path.write_text(json.dumps(asdict(cfg), indent=2) + "\n", encoding="utf-8")
        return cfg
    data = json.loads(path.read_text(encoding="utf-8"))
    return UpdateConfig(
        github_owner=str(data.get("github_owner") or DEFAULT_OWNER).strip(),
        github_repo=str(data.get("github_repo") or DEFAULT_REPO).strip(),
        release_ref=str(data.get("release_ref") or DEFAULT_REF).strip(),
        remote_url=str(data.get("remote_url") or DEFAULT_REMOTE).strip().rstrip("/"),
    )


def load_installed(install_root: Path) -> dict:
    path = installed_path(install_root)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_installed(install_root: Path, payload: dict) -> None:
    ensure_mailflow_dirs(install_root)
    installed_path(install_root).write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )


# Paths never replaced from a release package.
PRESERVE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".git",
        ".mailflow",
        ".venv",
        "node_modules",
        "storage",
        "audio",
        "launcher/.runtime",
    }
)

PRESERVE_PREFIXES = (
    ".env",
    "backend/.env",
    "backend/.venv",
    "backend/storage",
    "frontend/node_modules",
    "frontend/dist",
    "launcher/.runtime",
    ".mailflow/",
    "storage/",
)


def should_preserve_relative(rel: str) -> bool:
    normalized = rel.replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized in PRESERVE_NAMES or normalized.split("/")[0] in {
        ".git",
        ".mailflow",
        "audio",
        "node_modules",
    }:
        return True
    for prefix in PRESERVE_PREFIXES:
        if normalized == prefix.rstrip("/") or normalized.startswith(prefix):
            return True
    if normalized.endswith(".log"):
        return True
    return False
