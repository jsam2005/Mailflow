"""Public unauthenticated endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.unsubscribe_service import UnsubscribeService

router = APIRouter(prefix="/api/v1/public", tags=["public"])


class UnsubscribeResponse(BaseModel):
    status: str
    message: str


@router.get("/unsubscribe/{token}", response_model=UnsubscribeResponse)
def unsubscribe_preview(token: str, db: Session = Depends(get_db)) -> UnsubscribeResponse:
    """Validate token without confirming (safe for link preview / email clients)."""
    UnsubscribeService(db).verify_token(token)
    return UnsubscribeResponse(
        status="pending_confirmation",
        message="Confirm below to unsubscribe from future campaign emails.",
    )


@router.post("/unsubscribe/{token}", response_model=UnsubscribeResponse)
def unsubscribe_confirm(token: str, db: Session = Depends(get_db)) -> UnsubscribeResponse:
    UnsubscribeService(db).confirm(token)
    return UnsubscribeResponse(
        status="unsubscribed",
        message="You have been unsubscribed and will not receive further campaign emails.",
    )
