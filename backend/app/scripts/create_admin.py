"""Create an administrator user (required for production).

Usage:
  python -m app.scripts.create_admin --email admin@example.com --name Admin --password '...'
"""

from __future__ import annotations

import argparse
import getpass
import sys

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import User
from app.services.auth_service import AuthService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a MailFlow admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Admin")
    parser.add_argument("--password", default=None)
    args = parser.parse_args(argv)

    password = args.password or getpass.getpass("Password: ")
    if len(password) < 12:
        print("Password must be at least 12 characters.", file=sys.stderr)
        return 1

    settings = get_settings()
    if settings.is_production and password in {"admin123456", "password", "changeme"}:
        print("Refusing weak production password.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        existing = AuthService(db).get_by_email(args.email)
        if existing:
            print("A user with that email already exists.", file=sys.stderr)
            return 1
        user = User(
            name=args.name.strip(),
            email=args.email.lower().strip(),
            password_hash=hash_password(password),
        )
        db.add(user)
        db.commit()
        print(f"Created admin user: {user.email}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
