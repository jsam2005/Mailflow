"""Manual suppression management."""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.suppression import SuppressionReason
from app.models.user import User
from app.services.suppression_service import SuppressionService

router = APIRouter(prefix="/api/v1/suppressions", tags=["suppressions"])


class SuppressionCreate(BaseModel):
    email: EmailStr
    reason: str = SuppressionReason.MANUAL.value
    notes: str | None = Field(default=None, max_length=500)


class SuppressionResponse(BaseModel):
    id: UUID
    email: str
    normalized_email: str
    reason: str
    source: str | None
    created_at: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[SuppressionResponse])
def list_suppressions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SuppressionResponse]:
    rows = SuppressionService(db).list_for_user(current_user)
    return [
        SuppressionResponse(
            id=r.id,
            email=r.email,
            normalized_email=r.normalized_email,
            reason=r.reason,
            source=r.source,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.post("", response_model=SuppressionResponse, status_code=201)
def create_suppression(
    payload: SuppressionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SuppressionResponse:
    row = SuppressionService(db).suppress(
        current_user,
        str(payload.email),
        reason=payload.reason,
        source="manual",
        notes=payload.notes,
    )
    return SuppressionResponse(
        id=row.id,
        email=row.email,
        normalized_email=row.normalized_email,
        reason=row.reason,
        source=row.source,
        created_at=row.created_at.isoformat(),
    )


@router.delete("/{suppression_id}", status_code=204)
def delete_suppression(
    suppression_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    SuppressionService(db).remove(current_user, suppression_id)
