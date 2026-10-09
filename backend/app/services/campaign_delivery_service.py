"""Campaign start/pause/resume/cancel and delivery orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from uuid import UUID

from email.utils import make_msgid
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationAppError,
)
from app.core.logging import get_logger
from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_recipient import CampaignRecipient, CampaignRecipientStatus
from app.models.contact import Contact, ContactStatus
from app.models.email_account import ConnectionStatus, EmailAccount
from app.models.email_message import EmailMessage, EmailMessageStatus
from app.models.user import User
from app.schemas.campaigns import CampaignResponse, CampaignStatsResponse
from app.schemas.email_messages import EmailMessageResponse, PaginatedEmailMessagesResponse
from app.services.campaign.personalization import (
    UnresolvedPersonalizationError,
    apply_render_to_message,
    render_campaign_content,
)
from app.services.campaign.send_errors import NON_RETRYABLE_CODES
from app.services.campaign_service import CampaignService

logger = get_logger(__name__)

BATCH_SIZE = 500
INELIGIBLE_CONTACT = {
    ContactStatus.INVALID,
    ContactStatus.UNSUBSCRIBED,
    ContactStatus.SUPPRESSED,
    ContactStatus.BOUNCED,
}


class CampaignDeliveryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self._campaigns = CampaignService(db)

    def start(self, user: User, campaign_id: UUID) -> CampaignResponse:
        if not self.settings.campaign_sending_enabled:
            raise ServiceUnavailableError(
                "Campaign sending is disabled by configuration. "
                "Set CAMPAIGN_SENDING_ENABLED=true to enable."
            )

        campaign = self._campaigns._get_owned(user, campaign_id, load_relations=True)

        if campaign.status == CampaignStatus.RUNNING.value:
            raise ConflictError("Campaign is already running.")

        if campaign.status != CampaignStatus.READY.value:
            raise ValidationAppError("Only ready campaigns can be started.")

        validation = self._campaigns._validate(campaign, user)
        if not validation.valid:
            raise ValidationAppError(
                "Campaign cannot be started. " + "; ".join(validation.errors),
                details={"errors": validation.errors},
            )

        if not campaign.snapshot_subject or not campaign.snapshot_html:
            raise ValidationAppError("Campaign content snapshot is missing.")

        account = campaign.email_account
        if not account or not account.is_active:
            raise ValidationAppError("Email account is not active.")
        if account.connection_status != ConnectionStatus.CONNECTED.value:
            raise ValidationAppError("Email account is not connected.")

        now = datetime.now(UTC)
        campaign.status = CampaignStatus.RUNNING.value
        if not campaign.started_at:
            campaign.started_at = now
        campaign.paused_at = None
        campaign.last_activity_at = now

        recipients = list(
            self.db.scalars(
                select(CampaignRecipient)
                .where(
                    CampaignRecipient.campaign_id == campaign.id,
                    CampaignRecipient.status == CampaignRecipientStatus.PENDING.value,
                )
                .order_by(CampaignRecipient.id.asc())
            ).all()
        )
        if not recipients:
            raise ValidationAppError("No eligible recipients to send.")

        contact_ids = [r.contact_id for r in recipients]
        contacts = {
            c.id: c
            for c in self.db.scalars(
                select(Contact).where(Contact.id.in_(contact_ids))
            ).all()
        }

        created = 0
        batch: list[EmailMessage] = []
        for recipient in recipients:
            contact = contacts.get(recipient.contact_id)
            if not contact:
                continue
            to_name = None
            parts = [contact.first_name, contact.last_name]
            if any(parts):
                to_name = " ".join(p for p in parts if p and str(p).strip())

            try:
                rendered = render_campaign_content(
                    subject=campaign.snapshot_subject or "",
                    html=campaign.snapshot_html or "",
                    text=campaign.snapshot_plain_text,
                    contact=contact,
                    fallback_email=contact.email,
                    require_resolved=True,
                )
            except UnresolvedPersonalizationError as exc:
                raise ValidationAppError(
                    "Campaign content could not be personalized for all recipients. "
                    "Fix template variables before starting."
                ) from exc

            batch.append(
                EmailMessage(
                    user_id=user.id,
                    campaign_id=campaign.id,
                    campaign_recipient_id=recipient.id,
                    contact_id=contact.id,
                    email_account_id=account.id,
                    to_email=contact.email,
                    to_name=to_name,
                    subject=rendered.rendered_subject,
                    rendered_html=rendered.rendered_html,
                    rendered_text=rendered.rendered_text,
                    status=EmailMessageStatus.QUEUED.value,
                    max_attempts=self.settings.campaign_max_send_attempts,
                    next_attempt_at=now,
                )
            )
            recipient.status = CampaignRecipientStatus.QUEUED.value
            created += 1
            if len(batch) >= BATCH_SIZE:
                self.db.add_all(batch)
                self.db.flush()
                batch.clear()

        if batch:
            self.db.add_all(batch)

        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError("Campaign was already started.") from exc

        logger.info(
            "campaign.started",
            user_id=str(user.id),
            campaign_id=str(campaign.id),
            messages_created=created,
        )
        self.db.refresh(campaign)
        # Hobby has no frequent cron — process one batch immediately after start.
        self._kick_worker_batch(campaign_id=campaign.id)
        return self._campaigns.get(user, campaign.id)

    def pause(self, user: User, campaign_id: UUID) -> CampaignResponse:
        campaign = self._campaigns._get_owned(user, campaign_id, load_relations=True)
        if campaign.status != CampaignStatus.RUNNING.value:
            raise ValidationAppError("Only running campaigns can be paused.")
        campaign.status = CampaignStatus.PAUSED.value
        campaign.paused_at = datetime.now(UTC)
        campaign.last_activity_at = datetime.now(UTC)
        self.db.commit()
        logger.info("campaign.paused", user_id=str(user.id), campaign_id=str(campaign.id))
        return self._campaigns.get(user, campaign.id)

    def resume(self, user: User, campaign_id: UUID) -> CampaignResponse:
        if not self.settings.campaign_sending_enabled:
            raise ServiceUnavailableError(
                "Campaign sending is disabled by configuration."
            )
        campaign = self._campaigns._get_owned(user, campaign_id, load_relations=True)
        if campaign.status != CampaignStatus.PAUSED.value:
            raise ValidationAppError("Only paused campaigns can be resumed.")
        campaign.status = CampaignStatus.RUNNING.value
        campaign.paused_at = None
        campaign.last_activity_at = datetime.now(UTC)
        self.db.commit()
        logger.info("campaign.resumed", user_id=str(user.id), campaign_id=str(campaign.id))
        self._kick_worker_batch(campaign_id=campaign.id)
        return self._campaigns.get(user, campaign.id)

    def personalize_unsent_messages(self, user: User, campaign_id: UUID) -> dict:
        """Re-render stored content for queued (unsent) messages only. Never touches sent."""
        campaign = self._campaigns._get_owned(user, campaign_id, load_relations=True)
        subject_tpl = campaign.snapshot_subject or ""
        html_tpl = campaign.snapshot_html or ""
        text_tpl = campaign.snapshot_plain_text

        messages = list(
            self.db.scalars(
                select(EmailMessage)
                .where(
                    EmailMessage.campaign_id == campaign.id,
                    EmailMessage.status == EmailMessageStatus.QUEUED.value,
                )
                .order_by(EmailMessage.created_at.asc())
            ).all()
        )
        updated = 0
        failed = 0
        for message in messages:
            contact = self.db.get(Contact, message.contact_id)
            try:
                rendered = render_campaign_content(
                    subject=subject_tpl or message.subject,
                    html=html_tpl or (message.rendered_html or ""),
                    text=text_tpl if text_tpl is not None else message.rendered_text,
                    contact=contact,
                    fallback_email=message.to_email,
                    require_resolved=True,
                )
            except UnresolvedPersonalizationError:
                failed += 1
                logger.warning(
                    "campaign.personalize_unresolved",
                    campaign_id=str(campaign.id),
                    message_id=str(message.id),
                )
                continue
            apply_render_to_message(message, rendered)
            updated += 1
        self.db.commit()
        logger.info(
            "campaign.personalized_unsent",
            campaign_id=str(campaign.id),
            updated=updated,
            failed=failed,
        )
        return {"updated": updated, "failed": failed, "total_queued": len(messages)}

    def _kick_worker_batch(self, *, campaign_id: UUID) -> None:
        """Best-effort queue drain for Hobby (no minute-level cron)."""
        if self.settings.environment in {"test", "testing"}:
            return
        try:
            from app.workers.campaign_sender_worker import CampaignSenderWorker

            summary = CampaignSenderWorker(self.db).process_campaign_queue_batch()
            logger.info(
                "campaign.worker_kick",
                campaign_id=str(campaign_id),
                claimed=summary.get("claimed"),
                sent=summary.get("sent"),
                deferred=summary.get("deferred"),
                failed=summary.get("failed"),
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "campaign.worker_kick_failed",
                campaign_id=str(campaign_id),
            )

    def cancel(self, user: User, campaign_id: UUID) -> CampaignResponse:
        campaign = self._campaigns._get_owned(user, campaign_id, load_relations=True)
        allowed = {
            CampaignStatus.READY.value,
            CampaignStatus.RUNNING.value,
            CampaignStatus.PAUSED.value,
        }
        if campaign.status not in allowed:
            raise ValidationAppError(
                "Only ready, running, or paused campaigns can be cancelled."
            )

        now = datetime.now(UTC)
        campaign.status = CampaignStatus.CANCELLED.value
        campaign.cancelled_at = now
        campaign.last_activity_at = now

        self.db.execute(
            update(EmailMessage)
            .where(
                EmailMessage.campaign_id == campaign.id,
                EmailMessage.status.in_(
                    [
                        EmailMessageStatus.QUEUED.value,
                        EmailMessageStatus.SENDING.value,
                    ]
                ),
            )
            .values(
                status=EmailMessageStatus.CANCELLED.value,
                error_code="CAMPAIGN_CANCELLED",
                error_message="Campaign was cancelled.",
            )
        )
        self.db.execute(
            update(CampaignRecipient)
            .where(
                CampaignRecipient.campaign_id == campaign.id,
                CampaignRecipient.status.in_(
                    [
                        CampaignRecipientStatus.PENDING.value,
                        CampaignRecipientStatus.QUEUED.value,
                    ]
                ),
            )
            .values(
                status=CampaignRecipientStatus.CANCELLED.value,
                exclusion_reason="Campaign cancelled",
            )
        )
        self.db.commit()
        logger.info("campaign.cancelled", user_id=str(user.id), campaign_id=str(campaign.id))
        return self._campaigns.get(user, campaign.id)

    def retry_message(self, user: User, campaign_id: UUID, message_id: UUID) -> EmailMessageResponse:
        campaign = self._campaigns._get_owned(user, campaign_id)
        message = self.db.scalar(
            select(EmailMessage).where(
                EmailMessage.id == message_id,
                EmailMessage.campaign_id == campaign.id,
                EmailMessage.user_id == user.id,
            )
        )
        if not message:
            raise NotFoundError("Message not found.")
        if message.status != EmailMessageStatus.FAILED.value:
            raise ValidationAppError("Only failed messages can be retried.")
        if message.error_code == "UNCERTAIN_PROVIDER_RESULT":
            raise ValidationAppError(
                "This message cannot be retried automatically due to uncertain delivery."
            )
        if message.error_code in NON_RETRYABLE_CODES - {"UNKNOWN"}:
            if message.error_code not in {"RATE_LIMITED", "TEMPORARY_PROVIDER_ERROR", "QUOTA_EXCEEDED"}:
                raise ValidationAppError("This failure is not eligible for retry.")

        message.status = EmailMessageStatus.QUEUED.value
        message.next_attempt_at = datetime.now(UTC)
        message.error_code = None
        message.error_message = None
        message.failed_at = None
        self.db.commit()
        self.db.refresh(message)
        return EmailMessageResponse.model_validate(message)

    def list_messages(
        self,
        user: User,
        campaign_id: UUID,
        *,
        page: int = 1,
        page_size: int = 25,
        status: str | None = None,
        search: str | None = None,
    ) -> PaginatedEmailMessagesResponse:
        campaign = self._campaigns._get_owned(user, campaign_id)
        filters = [
            EmailMessage.campaign_id == campaign.id,
            EmailMessage.user_id == user.id,
        ]
        if status:
            filters.append(EmailMessage.status == status)
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    EmailMessage.to_email.ilike(term),
                    EmailMessage.to_name.ilike(term),
                    EmailMessage.subject.ilike(term),
                )
            )
        from sqlalchemy import and_

        where = and_(*filters)
        total = self.db.scalar(
            select(func.count()).select_from(EmailMessage).where(where)
        ) or 0
        rows = list(
            self.db.scalars(
                select(EmailMessage)
                .where(where)
                .order_by(EmailMessage.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PaginatedEmailMessagesResponse(
            items=[EmailMessageResponse.model_validate(m) for m in rows],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get_message(
        self,
        user: User,
        campaign_id: UUID,
        message_id: UUID,
    ) -> EmailMessageResponse:
        campaign = self._campaigns._get_owned(user, campaign_id)
        message = self.db.scalar(
            select(EmailMessage).where(
                EmailMessage.id == message_id,
                EmailMessage.campaign_id == campaign.id,
                EmailMessage.user_id == user.id,
            )
        )
        if not message:
            raise NotFoundError("Message not found.")
        return EmailMessageResponse.model_validate(message)

    def build_delivery_stats(self, campaign: Campaign) -> dict:
        """Augment recipient stats with message-level delivery metrics."""
        msg_rows = self.db.execute(
            select(EmailMessage.status, func.count())
            .where(EmailMessage.campaign_id == campaign.id)
            .group_by(EmailMessage.status)
        ).all()
        by_msg = {status: count for status, count in msg_rows}
        messages_total = sum(by_msg.values())
        sent = by_msg.get(EmailMessageStatus.SENT.value, 0)
        failed = by_msg.get(EmailMessageStatus.FAILED.value, 0)
        cancelled = by_msg.get(EmailMessageStatus.CANCELLED.value, 0)
        queued = by_msg.get(EmailMessageStatus.QUEUED.value, 0)
        sending = by_msg.get(EmailMessageStatus.SENDING.value, 0)

        processed = sent + failed + cancelled
        progress = 0.0
        if messages_total > 0:
            progress = min(100.0, round(100.0 * processed / messages_total, 2))

        return {
            "messages_total": messages_total,
            "messages_queued": queued,
            "messages_sending": sending,
            "messages_sent": sent,
            "messages_failed": failed,
            "messages_cancelled": cancelled,
            "progress_percent": progress,
            "started_at": campaign.started_at,
            "completed_at": campaign.completed_at,
            "last_activity_at": campaign.last_activity_at,
        }

    @staticmethod
    def assign_rfc_message_id(message: EmailMessage) -> str:
        if message.rfc_message_id:
            return message.rfc_message_id
        rfc_id = make_msgid(domain="mailflow.local")
        message.rfc_message_id = rfc_id
        return rfc_id

    @staticmethod
    def contact_no_longer_eligible(contact: Contact) -> bool:
        status = contact.status
        if isinstance(status, ContactStatus):
            return status in INELIGIBLE_CONTACT
        try:
            return ContactStatus(str(status)) in INELIGIBLE_CONTACT
        except ValueError:
            return True
