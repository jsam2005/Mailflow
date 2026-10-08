"""Development seed data. Refuses to run in production.

Usage (from backend/):
  ENVIRONMENT=development python scripts/seed_dev.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("ENVIRONMENT", "development")

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User
from app.services.auth_service import AuthService


def main() -> int:
    settings = get_settings()
    if settings.is_production:
        print("Refusing to seed development data in production.", file=sys.stderr)
        return 1
    if settings.environment not in {"development", "test"}:
        print("Seed only allowed for development/test.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        email = settings.admin_email or "admin@example.com"
        password = settings.admin_password or "dev-only-change-me"
        AuthService(db).ensure_admin_user(
            name=settings.admin_name or "Admin",
            email=email,
            password=password,
        )
        print(f"Dev admin ready: {email}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
