"""Authentication routes."""

import os

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.security import create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.auth_service import AuthService
from app.services.rate_limit_service import RateLimitService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    settings = get_settings()
    client = request.client.host if request.client else "unknown"
    RateLimitService(db).check_and_hit(
        f"login:{client}:{body.email.lower().strip()}",
        limit=settings.login_rate_limit_per_minute,
        window_seconds=60,
    )
    user, token = AuthService(db).authenticate(body.email, body.password)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


DESKTOP_SESSION_HEADER = "X-MailFlow-Desktop"
_DESKTOP_HOSTS = {"127.0.0.1", "localhost"}


def _client_host(request: Request) -> str:
    return request.client.host if request.client else ""


def _is_desktop_request(request: Request) -> bool:
    """Only the desktop app's own page on loopback may open a session.

    The custom header forces a CORS preflight, so other websites cannot call
    this from a browser. The Host and Origin checks block DNS rebinding.
    """
    if os.environ.get("MAILFLOW_DESKTOP") != "1":
        return False
    if request.headers.get(DESKTOP_SESSION_HEADER) != "1":
        return False
    if _client_host(request) not in {"127.0.0.1", "::1"}:
        return False
    host = (request.headers.get("host") or "").rsplit(":", 1)[0]
    if host not in _DESKTOP_HOSTS:
        return False
    origin = request.headers.get("origin")
    if origin:
        origin_host = origin.split("://", 1)[-1].rsplit(":", 1)[0]
        if origin_host not in _DESKTOP_HOSTS:
            return False
    return True


@router.post("/desktop-session", response_model=TokenResponse, include_in_schema=False)
def desktop_session(request: Request, db: Session = Depends(get_db)) -> TokenResponse:
    """Sign the desktop app straight in as its local admin (desktop mode only)."""
    if not _is_desktop_request(request):
        raise NotFoundError("Not found")
    settings = get_settings()
    user = None
    if settings.admin_email:
        user = AuthService(db).get_by_email(settings.admin_email)
    if user is None:
        user = db.scalar(select(User).order_by(User.created_at).limit(1))
    if user is None:
        raise NotFoundError("Not found")
    token = create_access_token(user.id, extra_claims={"email": user.email})
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))
