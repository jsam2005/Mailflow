"""Contact list API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.contact import ContactCreate, ContactResponse
from app.schemas.contact_list import (
    ContactListCreate,
    ContactListResponse,
    ContactListUpdate,
)
from app.services.contact_list_service import ContactListService
from app.services.contact_service import ContactService

router = APIRouter(prefix="/api/v1/contact-lists", tags=["contact-lists"])


@router.post("", response_model=ContactListResponse, status_code=201)
def create_contact_list(
    body: ContactListCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactListResponse:
    contact_list = ContactListService(db).create_contact_list(current_user, body)
    return ContactListResponse.model_validate(contact_list)


@router.get("", response_model=list[ContactListResponse])
def list_contact_lists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ContactListResponse]:
    lists = ContactListService(db).get_contact_lists(current_user)
    return [ContactListResponse.model_validate(item) for item in lists]


@router.get("/{list_id}", response_model=ContactListResponse)
def get_contact_list(
    list_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactListResponse:
    contact_list = ContactListService(db).get_contact_list(current_user, list_id)
    return ContactListResponse.model_validate(contact_list)


@router.put("/{list_id}", response_model=ContactListResponse)
def update_contact_list(
    list_id: UUID,
    body: ContactListUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactListResponse:
    contact_list = ContactListService(db).update_contact_list(current_user, list_id, body)
    return ContactListResponse.model_validate(contact_list)


@router.delete("/{list_id}", status_code=204)
def delete_contact_list(
    list_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    ContactListService(db).delete_contact_list(current_user, list_id)


@router.post(
    "/{list_id}/contacts",
    response_model=ContactResponse,
    status_code=201,
)
def create_contact_in_list(
    list_id: UUID,
    body: ContactCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContactResponse:
    contact = ContactService(db).create_contact(current_user, list_id, body)
    # Reload with list relationship for response
    contact = ContactService(db).get_contact(current_user, contact.id)
    return ContactService._to_response(contact)
