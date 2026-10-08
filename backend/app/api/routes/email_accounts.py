"""Email account configuration and Gmail OAuth routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.email_accounts import (
    ConnectionTestResponse,
    EmailAccountListResponse,
    EmailAccountResponse,
    EmailAccountUpdate,
    GoogleConnectResponse,
    SendTestEmailRequest,
    SendTestEmailResponse,
)
from app.services.email_account_service import EmailAccountService

router = APIRouter(prefix="/api/v1/email-accounts", tags=["email-accounts"])


@router.get("", response_model=EmailAccountListResponse)
def list_email_accounts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmailAccountListResponse:
    return EmailAccountService(db).list_accounts(current_user)


@router.post("/google/connect", response_model=GoogleConnectResponse)
def connect_google(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoogleConnectResponse:
    return EmailAccountService(db).start_google_connect(current_user)


@router.get("/google/callback")
def google_oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Public callback — user binding comes from server-side OAuth state only."""
    redirect_url = EmailAccountService(db).handle_google_callback(
        code=code,
        state=state,
        error=error,
    )
    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/{account_id}", response_model=EmailAccountResponse)
def get_email_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmailAccountResponse:
    return EmailAccountService(db).get_account(current_user, account_id)


@router.put("/{account_id}", response_model=EmailAccountResponse)
def update_email_account(
    account_id: UUID,
    body: EmailAccountUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmailAccountResponse:
    return EmailAccountService(db).update_account(current_user, account_id, body)


@router.delete("/{account_id}", status_code=204)
def disconnect_email_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    EmailAccountService(db).disconnect(current_user, account_id)


@router.post("/{account_id}/test-connection", response_model=ConnectionTestResponse)
def test_connection(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConnectionTestResponse:
    return EmailAccountService(db).test_connection(current_user, account_id)


@router.post("/{account_id}/send-test", response_model=SendTestEmailResponse)
def send_test_email(
    account_id: UUID,
    body: SendTestEmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SendTestEmailResponse:
    return EmailAccountService(db).send_test_email(current_user, account_id, body)


@router.post("/{account_id}/reconnect", response_model=GoogleConnectResponse)
def reconnect_email_account(
    account_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> GoogleConnectResponse:
    return EmailAccountService(db).reconnect(current_user, account_id)
