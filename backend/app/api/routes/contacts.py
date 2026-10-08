"""Contact API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.contact import ContactStatus
from app.models.user import User
from app.schemas.contact import (
    ContactBulkDeleteRequest,
    ContactBulkDeleteResponse,
    ContactResponse,
    ContactStatsResponse,
    ContactUpdate,
    PaginatedContactResponse,
)
from app.services.contact_service import ContactService

router = APIRouter(prefix="/api/v1/contacts", tags=["contacts"])


@router.get("/stats", response_model=ContactStatsResponse)
def contact_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactStatsResponse:
    return ContactService(db).get_stats(current_user)


@router.post("/bulk-delete", response_model=ContactBulkDeleteResponse)
def bulk_delete_contacts(
    body: ContactBulkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactBulkDeleteResponse:
    deleted = ContactService(db).bulk_delete_contacts(current_user, body.contact_ids)
    return ContactBulkDeleteResponse(deleted=deleted)


@router.get("", response_model=PaginatedContactResponse)
def list_contacts(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None),
    status: ContactStatus | None = Query(default=None),
    company: str | None = Query(default=None),
    contact_list_id: UUID | None = Query(default=None),
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedContactResponse:
    allowed_sort = {"created_at", "email", "first_name", "last_name", "company", "status"}
    if sort_by not in allowed_sort:
        sort_by = "created_at"
    if sort_order.lower() not in {"asc", "desc"}:
        sort_order = "desc"

    return ContactService(db).list_contacts(
        current_user,
        page=page,
        page_size=page_size,
        search=search,
        status=status,
        company=company,
        contact_list_id=contact_list_id,
        sort_by=sort_by,
        sort_order=sort_order.lower(),
    )


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactResponse:
    contact = ContactService(db).get_contact(current_user, contact_id)
    return ContactService._to_response(contact)


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: UUID,
    body: ContactUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactResponse:
    contact = ContactService(db).update_contact(current_user, contact_id, body)
    contact = ContactService(db).get_contact(current_user, contact.id)
    return ContactService._to_response(contact)


@router.delete("/{contact_id}", status_code=204)
def delete_contact(
    contact_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ContactService(db).delete_contact(current_user, contact_id)
