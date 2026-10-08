"""Contact domain service."""

from math import ceil
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.models.contact import Contact, ContactStatus
from app.models.contact_list import ContactList
from app.models.user import User
from app.schemas.contact import (
    ContactCreate,
    ContactStatsResponse,
    ContactUpdate,
    PaginatedContactResponse,
)
from app.schemas.contact import ContactResponse
from app.services.contact_list_service import ContactListService
from app.utils.email import validate_and_normalize_email

logger = get_logger(__name__)

SORT_COLUMNS = {
    "created_at": Contact.created_at,
    "email": Contact.normalized_email,
    "first_name": Contact.first_name,
    "last_name": Contact.last_name,
    "company": Contact.company,
    "status": Contact.status,
}


class ContactService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.list_service = ContactListService(db)

    def create_contact(
        self,
        user: User,
        list_id: UUID,
        data: ContactCreate,
    ) -> Contact:
        contact_list = self.list_service.get_contact_list(user, list_id)
        display_email, normalized = validate_and_normalize_email(data.email)

        if self._find_duplicate(list_id, normalized):
            raise ConflictError(
                "A contact with this email already exists in this list",
                details={"email": normalized},
            )

        contact = Contact(
            contact_list_id=contact_list.id,
            email=display_email,
            normalized_email=normalized,
            first_name=self._clean_optional(data.first_name),
            last_name=self._clean_optional(data.last_name),
            company=self._clean_optional(data.company),
            phone=self._clean_optional(data.phone),
            website=self._clean_optional(data.website),
            status=ContactStatus.ACTIVE,
            contact_metadata=data.contact_metadata or {},
        )
        self.db.add(contact)
        try:
            self.db.flush()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "A contact with this email already exists in this list",
                details={"email": normalized},
            ) from exc

        contact_list.total_contacts = (contact_list.total_contacts or 0) + 1
        self.db.commit()
        self.db.refresh(contact)
        logger.info(
            "contact.created",
            user_id=str(user.id),
            contact_id=str(contact.id),
            contact_list_id=str(list_id),
        )
        return contact

    def get_contact(self, user: User, contact_id: UUID) -> Contact:
        return self._get_owned_contact(user, contact_id)

    def list_contacts(
        self,
        user: User,
        *,
        page: int = 1,
        page_size: int = 25,
        search: str | None = None,
        status: ContactStatus | None = None,
        company: str | None = None,
        contact_list_id: UUID | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> PaginatedContactResponse:
        filters = [ContactList.user_id == user.id]

        if contact_list_id is not None:
            # Ensure the list belongs to the user before filtering
            self.list_service.get_contact_list(user, contact_list_id)
            filters.append(Contact.contact_list_id == contact_list_id)

        if status is not None:
            filters.append(Contact.status == status)

        if company:
            filters.append(Contact.company.ilike(f"%{company.strip()}%"))

        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    Contact.email.ilike(term),
                    Contact.normalized_email.ilike(term),
                    Contact.first_name.ilike(term),
                    Contact.last_name.ilike(term),
                    Contact.company.ilike(term),
                )
            )

        where_clause = and_(*filters)
        count_stmt = (
            select(func.count())
            .select_from(Contact)
            .join(ContactList, Contact.contact_list_id == ContactList.id)
            .where(where_clause)
        )
        total = self.db.scalar(count_stmt) or 0

        sort_column = SORT_COLUMNS.get(sort_by, Contact.created_at)
        order = sort_column.asc() if sort_order == "asc" else sort_column.desc()

        offset = (page - 1) * page_size
        stmt = (
            select(Contact)
            .join(ContactList, Contact.contact_list_id == ContactList.id)
            .options(joinedload(Contact.contact_list))
            .where(where_clause)
            .order_by(order, Contact.id.asc())
            .offset(offset)
            .limit(page_size)
        )
        contacts = list(self.db.scalars(stmt).unique().all())
        total_pages = ceil(total / page_size) if total > 0 else 0

        items = [self._to_response(contact) for contact in contacts]
        return PaginatedContactResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )

    def update_contact(
        self,
        user: User,
        contact_id: UUID,
        data: ContactUpdate,
    ) -> Contact:
        contact = self._get_owned_contact(user, contact_id)

        if data.email is not None:
            display_email, normalized = validate_and_normalize_email(data.email)
            if normalized != contact.normalized_email:
                if self._find_duplicate(contact.contact_list_id, normalized, exclude_id=contact.id):
                    raise ConflictError(
                        "A contact with this email already exists in this list",
                        details={"email": normalized},
                    )
            contact.email = display_email
            contact.normalized_email = normalized

        if data.first_name is not None:
            contact.first_name = self._clean_optional(data.first_name)
        if data.last_name is not None:
            contact.last_name = self._clean_optional(data.last_name)
        if data.company is not None:
            contact.company = self._clean_optional(data.company)
        if data.phone is not None:
            contact.phone = self._clean_optional(data.phone)
        if data.website is not None:
            contact.website = self._clean_optional(data.website)
        if data.status is not None:
            contact.status = data.status
        if data.contact_metadata is not None:
            contact.contact_metadata = data.contact_metadata

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "A contact with this email already exists in this list",
            ) from exc

        self.db.refresh(contact)
        logger.info(
            "contact.updated",
            user_id=str(user.id),
            contact_id=str(contact.id),
        )
        return contact

    def set_contact_status(
        self,
        user: User,
        contact_id: UUID,
        status: ContactStatus,
    ) -> Contact:
        return self.update_contact(
            user,
            contact_id,
            ContactUpdate(status=status),
        )

    def delete_contact(self, user: User, contact_id: UUID) -> None:
        contact = self._get_owned_contact(user, contact_id)
        list_id = contact.contact_list_id
        self.db.delete(contact)
        self.db.flush()
        self.list_service.recalculate_contact_list_total(list_id)
        logger.info(
            "contact.deleted",
            user_id=str(user.id),
            contact_id=str(contact_id),
        )

    def bulk_delete_contacts(self, user: User, contact_ids: list[UUID]) -> int:
        if not contact_ids:
            raise ValidationAppError("No contact IDs provided")

        stmt = (
            select(Contact)
            .join(ContactList, Contact.contact_list_id == ContactList.id)
            .where(
                ContactList.user_id == user.id,
                Contact.id.in_(contact_ids),
            )
        )
        contacts = list(self.db.scalars(stmt).all())
        if len(contacts) != len(set(contact_ids)):
            raise NotFoundError("One or more contacts were not found")

        list_ids = {contact.contact_list_id for contact in contacts}
        for contact in contacts:
            self.db.delete(contact)

        self.db.flush()
        for list_id in list_ids:
            self.list_service.recalculate_contact_list_total(list_id)

        logger.info(
            "contact.bulk_deleted",
            user_id=str(user.id),
            deleted=len(contacts),
        )
        return len(contacts)

    def get_stats(self, user: User) -> ContactStatsResponse:
        base = (
            select(Contact.status, func.count())
            .join(ContactList, Contact.contact_list_id == ContactList.id)
            .where(ContactList.user_id == user.id)
            .group_by(Contact.status)
        )
        rows = self.db.execute(base).all()
        counts = {status.value if isinstance(status, ContactStatus) else status: count for status, count in rows}

        list_count = self.db.scalar(
            select(func.count())
            .select_from(ContactList)
            .where(ContactList.user_id == user.id)
        ) or 0

        total = sum(counts.values())
        return ContactStatsResponse(
            total=total,
            active=counts.get(ContactStatus.ACTIVE.value, 0),
            invalid=counts.get(ContactStatus.INVALID.value, 0),
            unsubscribed=counts.get(ContactStatus.UNSUBSCRIBED.value, 0),
            bounced=counts.get(ContactStatus.BOUNCED.value, 0),
            suppressed=counts.get(ContactStatus.SUPPRESSED.value, 0),
            contact_lists=list_count,
        )

    def _get_owned_contact(self, user: User, contact_id: UUID) -> Contact:
        stmt = (
            select(Contact)
            .join(ContactList, Contact.contact_list_id == ContactList.id)
            .options(joinedload(Contact.contact_list))
            .where(Contact.id == contact_id, ContactList.user_id == user.id)
        )
        contact = self.db.scalar(stmt)
        if contact is None:
            raise NotFoundError("Contact not found")
        return contact

    def _find_duplicate(
        self,
        list_id: UUID,
        normalized_email: str,
        exclude_id: UUID | None = None,
    ) -> Contact | None:
        stmt = select(Contact).where(
            Contact.contact_list_id == list_id,
            Contact.normalized_email == normalized_email,
        )
        if exclude_id is not None:
            stmt = stmt.where(Contact.id != exclude_id)
        return self.db.scalar(stmt)

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _to_response(contact: Contact) -> ContactResponse:
        return ContactResponse(
            id=contact.id,
            contact_list_id=contact.contact_list_id,
            contact_list_name=contact.contact_list.name if contact.contact_list else None,
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
            company=contact.company,
            phone=contact.phone,
            website=contact.website,
            status=contact.status,
            contact_metadata=contact.contact_metadata or {},
            created_at=contact.created_at,
            updated_at=contact.updated_at,
        )
