"""Pytest fixtures for MailFlow API tests."""

import os
from collections.abc import Generator
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Configure test environment before app imports
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production-use-only"
os.environ["TOKEN_ENCRYPTION_KEY"] = "I_1WmUSBsquzW12HDIFVXjBnygdlDdlF82xrmaualtU="
os.environ["GOOGLE_CLIENT_ID"] = "test-google-client-id"
os.environ["GOOGLE_CLIENT_SECRET"] = "test-google-client-secret"
os.environ["GOOGLE_REDIRECT_URI"] = (
    "http://localhost:8000/api/v1/email-accounts/google/callback"
)
os.environ["TEST_EMAIL_HOURLY_LIMIT"] = "10"
os.environ["ADMIN_EMAIL"] = "admin@example.com"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["ADMIN_NAME"] = "Test Admin"
os.environ["FRONTEND_URL"] = "http://localhost:5173"
os.environ["STORAGE_PATH"] = "/tmp/mailflow-test-storage"
os.environ["STORAGE_PROVIDER"] = "local"
os.environ["CAMPAIGN_SENDING_ENABLED"] = "true"
os.environ["CRON_SECRET"] = "test-cron-secret-at-least-32-characters"
os.environ["ENABLE_LOCAL_SCHEDULER"] = "false"

# Prefer isolated TEST_DATABASE_URL; never point tests at a production host.
_test_db = os.environ.get("TEST_DATABASE_URL", "").strip()
if _test_db:
    os.environ["DATABASE_URL"] = _test_db
else:
    os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

_db_url = os.environ["DATABASE_URL"]
_db_host = (urlparse(_db_url).hostname or "").lower()
_blocked_hosts = {
    "neon.tech",
    "amazonaws.com",
    "supabase.co",
    "railway.app",
    "render.com",
}
if any(marker in _db_url.lower() for marker in _blocked_hosts) or (
    _db_host and _db_host not in {"localhost", "127.0.0.1", ""} and "sqlite" not in _db_url
):
    # Allow only sqlite or explicit local postgres for tests.
    if "sqlite" not in _db_url and _db_host not in {"localhost", "127.0.0.1"}:
        raise RuntimeError(
            "Refusing to run pytest against a non-local DATABASE_URL. "
            "Set TEST_DATABASE_URL to a local/test database or omit it for in-memory SQLite."
        )

from app.core.config import get_settings
from app.services.token_encryption_service import get_token_encryption

get_settings.cache_clear()
get_token_encryption.cache_clear()

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine, get_db
from app.main import create_app
from app.models.user import User


@pytest.fixture(autouse=True)
def setup_database() -> Generator[None, None, None]:
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db
        finally:
            pass

    application = create_app()
    application.dependency_overrides[get_db] = override_get_db

    with TestClient(application) as test_client:
        yield test_client

    application.dependency_overrides.clear()


def _ensure_user(db: Session, *, name: str, email: str, password: str) -> User:
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return existing
    user = User(name=name, email=email, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def admin_user(db: Session) -> User:
    return _ensure_user(
        db,
        name="Test Admin",
        email="admin@example.com",
        password="test-admin-password",
    )


@pytest.fixture()
def other_user(db: Session) -> User:
    return _ensure_user(
        db,
        name="Other User",
        email="other@example.com",
        password="other-password",
    )


@pytest.fixture()
def auth_headers(client: TestClient, admin_user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "test-admin-password"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def other_auth_headers(client: TestClient, other_user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": other_user.email, "password": "other-password"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
