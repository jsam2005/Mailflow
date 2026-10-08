"""Contact list domain service."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.contact_list import ContactList
from app.models.user import User
from app.schemas.contact_list import ContactListCreate, ContactListUpdate

logger = get_logger(__name__)


class ContactListService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_contact_list(self, user: User, data: ContactListCreate) -> ContactList:
        contact_list = ContactList(
            user_id=user.id,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            total_contacts=0,
        )
        self.db.add(contact_list)
        self.db.commit()
        self.db.refresh(contact_list)
        logger.info(
            "contact_list.created",
            user_id=str(user.id),
            contact_list_id=str(contact_list.id),
        )
        return contact_list

    def get_contact_lists(self, user: User) -> list[ContactList]:
        stmt = (
            select(ContactList)
            .where(ContactList.user_id == user.id)
            .order_by(ContactList.created_at.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get_contact_list(self, user: User, list_id: UUID) -> ContactList:
        contact_list = self._get_owned_list(user, list_id)
        return contact_list

    def update_contact_list(
        self,
        user: User,
        list_id: UUID,
        data: ContactListUpdate,
    ) -> ContactList:
        contact_list = self._get_owned_list(user, list_id)
        if data.name is not None:
            contact_list.name = data.name.strip()
        if data.description is not None:
            contact_list.description = data.description.strip() or None

        self.db.commit()
        self.db.refresh(contact_list)
        logger.info(
            "contact_list.updated",
            user_id=str(user.id),
            contact_list_id=str(contact_list.id),
        )
        return contact_list

    def delete_contact_list(self, user: User, list_id: UUID) -> None:
        """
        Delete a contact list and all contacts in that list.

        Cascade is enforced at the database FK level and ORM relationship.
        """
        contact_list = self._get_owned_list(user, list_id)
        list_uuid = contact_list.id
        self.db.delete(contact_list)
        self.db.commit()
        logger.info(
            "contact_list.deleted",
            user_id=str(user.id),
            contact_list_id=str(list_uuid),
        )

    def recalculate_contact_list_total(self, contact_list_id: UUID) -> int:
        count = self.db.scalar(
            select(func.count())
            .select_from(Contact)
            .where(Contact.contact_list_id == contact_list_id)
        ) or 0
        contact_list = self.db.get(ContactList, contact_list_id)
        if contact_list is not None:
            contact_list.total_contacts = count
            self.db.commit()
        return count

    def _get_owned_list(self, user: User, list_id: UUID) -> ContactList:
        stmt = (
            select(ContactList)
            .where(ContactList.id == list_id, ContactList.user_id == user.id)
            .options(selectinload(ContactList.contacts))
        )
        contact_list = self.db.scalar(stmt)
        if contact_list is None:
            raise NotFoundError("Contact list not found")
        return contact_list
