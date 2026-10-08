"""Per-user email suppression."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.models.campaign_recipient import CampaignRecipient, CampaignRecipientStatus
from app.models.contact import Contact, ContactStatus
from app.models.contact_list import ContactList
from app.models.email_message import EmailMessage, EmailMessageStatus
from app.models.suppression import SuppressionList, SuppressionReason
from app.models.user import User

logger = get_logger(__name__)


def normalize_email(email: str) -> str:
    return email.strip().lower()


class SuppressionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def is_suppressed(self, user_id: UUID, email: str) -> bool:
        normalized = normalize_email(email)
        row = self.db.scalar(
            select(SuppressionList.id).where(
                SuppressionList.user_id == user_id,
                SuppressionList.normalized_email == normalized,
            )
        )
        return row is not None

    def suppress(
        self,
        user: User,
        email: str,
        *,
        reason: str,
        source: str | None = None,
        notes: str | None = None,
        cancel_queued: bool = True,
    ) -> SuppressionList:
        normalized = normalize_email(email)
        if not normalized or "@" not in normalized:
            raise ValidationAppError("A valid email is required.")
        if reason not in {r.value for r in SuppressionReason}:
            raise ValidationAppError("Invalid suppression reason.")

        existing = self.db.scalar(
            select(SuppressionList).where(
                SuppressionList.user_id == user.id,
                SuppressionList.normalized_email == normalized,
            )
        )
        if existing:
            raise ConflictError("Email is already suppressed.")

        row = SuppressionList(
            user_id=user.id,
            email=email.strip(),
            normalized_email=normalized,
            reason=reason,
            source=source,
            notes=notes,
        )
        self.db.add(row)

        contacts = list(
            self.db.scalars(
                select(Contact)
                .join(ContactList, ContactList.id == Contact.contact_list_id)
                .where(
                    ContactList.user_id == user.id,
                    Contact.normalized_email == normalized,
                )
            ).all()
        )
        for contact in contacts:
            contact.status = ContactStatus.UNSUBSCRIBED

        if cancel_queued:
            self._cancel_queued_for_email(user.id, normalized)

        self.db.commit()
        self.db.refresh(row)
        logger.info(
            "suppression.created",
            user_id=str(user.id),
            reason=reason,
            source=source,
        )
        return row

    def _cancel_queued_for_email(self, user_id: UUID, normalized: str) -> None:
        messages = list(
            self.db.scalars(
                select(EmailMessage).where(
                    EmailMessage.user_id == user_id,
                    EmailMessage.to_email == normalized,
                    EmailMessage.status.in_(
                        [
                            EmailMessageStatus.QUEUED.value,
                            EmailMessageStatus.SENDING.value,
                        ]
                    ),
                )
            ).all()
        )
        # also match case variants
        if not messages:
            messages = list(
                self.db.scalars(
                    select(EmailMessage).where(
                        EmailMessage.user_id == user_id,
                        EmailMessage.status.in_(
                            [
                                EmailMessageStatus.QUEUED.value,
                                EmailMessageStatus.SENDING.value,
                            ]
                        ),
                    )
                ).all()
            )
            messages = [m for m in messages if normalize_email(m.to_email) == normalized]

        for message in messages:
            message.status = EmailMessageStatus.CANCELLED.value
            message.error_code = "SUPPRESSED"
            message.error_message = "Recipient was suppressed."
            recipient = self.db.get(CampaignRecipient, message.campaign_recipient_id)
            if recipient:
                recipient.status = CampaignRecipientStatus.SUPPRESSED.value
                recipient.exclusion_reason = "Suppressed"

    def list_for_user(self, user: User) -> list[SuppressionList]:
        return list(
            self.db.scalars(
                select(SuppressionList)
                .where(SuppressionList.user_id == user.id)
                .order_by(SuppressionList.created_at.desc())
            ).all()
        )

    def remove(self, user: User, suppression_id: UUID) -> None:
        row = self.db.scalar(
            select(SuppressionList).where(
                SuppressionList.id == suppression_id,
                SuppressionList.user_id == user.id,
            )
        )
        if not row:
            raise NotFoundError("Suppression entry not found.")
        self.db.delete(row)
        self.db.commit()
