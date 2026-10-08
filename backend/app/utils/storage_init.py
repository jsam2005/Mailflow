"""Ensure local storage directories exist at startup."""

from pathlib import Path

from app.core.logging import get_logger

logger = get_logger(__name__)

REQUIRED_SUBDIRS = ("imports", "template-images", "attachments")


def ensure_storage_dirs(storage_path: str | Path) -> None:
    root = Path(storage_path)
    root.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_SUBDIRS:
        (root / name).mkdir(parents=True, exist_ok=True)
    logger.info("storage.dirs_ready", path=str(root))
