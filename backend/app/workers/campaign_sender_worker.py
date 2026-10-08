"""Background campaign email sender (APScheduler tick)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.exceptions import OAuthError, ValidationAppError
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_recipient import CampaignRecipient, CampaignRecipientStatus
from app.models.contact import Contact
from app.models.email_account import ConnectionStatus, EmailAccount
from app.models.email_message import EmailMessage, EmailMessageStatus
from app.services.campaign.rate_limits import RateLimitService, effective_limits
from app.services.campaign.send_errors import (
    classify_exception,
    retry_delay_seconds,
)
from app.services.campaign_delivery_service import CampaignDeliveryService
from app.services.email.email_message_builder import EmailMessageBuilder
from app.services.email.gmail_provider import GmailProvider
from app.services.email_account_service import EmailAccountService
from app.services.template_render_service import RenderContext, TemplateRenderService
from app.utils.html_sanitize import sanitize_email_html
from app.utils.plain_text import html_to_plain_text
from app.workers import worker_state

logger = get_logger(__name__)


class CampaignSenderWorker:
    def __init__(
        self,
        db: Session | None = None,
        *,
        gmail: GmailProvider | None = None,
    ) -> None:
        self._external_db = db
        self.settings = get_settings()
        self.gmail = gmail or GmailProvider(self.settings)
        self.renderer = TemplateRenderService()

    def tick(self) -> dict:
        """APScheduler entrypoint — delegates to process_campaign_queue_batch."""
        return self.process_campaign_queue_batch()

    def process_campaign_queue_batch(self) -> dict:
        """Process a bounded batch of eligible campaign messages (scheduler or cron)."""
        started = datetime.now(UTC)
        worker_state.last_worker_tick = started
        summary = {
            "claimed": 0,
            "sent": 0,
            "failed": 0,
            "deferred": 0,
            "cancelled": 0,
            "completed_campaigns": 0,
            "sending_enabled": self.settings.campaign_sending_enabled,
            "execution_ms": 0,
        }
        db = self._external_db or SessionLocal()
        close_db = self._external_db is None
        try:
            self._recover_stale_sending(db)
            if not self.settings.campaign_sending_enabled:
                db.commit()
                summary["execution_ms"] = int(
                    (datetime.now(UTC) - started).total_seconds() * 1000
                )
                return summary

            rate_limits = RateLimitService(db, self.settings)
            accounts_with_sending = set(
                db.scalars(
                    select(EmailMessage.email_account_id)
                    .where(EmailMessage.status == EmailMessageStatus.SENDING.value)
                    .distinct()
                ).all()
            )

            while summary["claimed"] < self.settings.campaign_worker_batch_size:
                message = self._pick_next_message(db, accounts_with_sending)
                if message is None:
                    break
                if not self._claim_message(db, message):
                    continue
                accounts_with_sending.add(message.email_account_id)
                summary["claimed"] += 1
                before = message.status
                self._process_claimed_message(db, message, rate_limits)
                # Session uses autoflush=False — flush so status changes persist
                # before any subsequent queries / refresh.
                db.flush()
                if message.status == EmailMessageStatus.SENT.value:
                    summary["sent"] += 1
                elif message.status == EmailMessageStatus.FAILED.value:
                    summary["failed"] += 1
                elif message.status == EmailMessageStatus.CANCELLED.value:
                    summary["cancelled"] += 1
                elif message.status == EmailMessageStatus.QUEUED.value:
                    summary["deferred"] += 1
                elif before != message.status:
                    summary["deferred"] += 1

            completed_before = {
                c.id
                for c in db.scalars(
                    select(Campaign).where(Campaign.status == CampaignStatus.COMPLETED.value)
                ).all()
            }
            self._check_completions(db)
            completed_after = {
                c.id
                for c in db.scalars(
                    select(Campaign).where(Campaign.status == CampaignStatus.COMPLETED.value)
                ).all()
            }
            summary["completed_campaigns"] = len(completed_after - completed_before)
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("campaign_worker.tick_failed")
        finally:
            if close_db:
                db.close()
        summary["execution_ms"] = int(
            (datetime.now(UTC) - started).total_seconds() * 1000
        )
        return summary

    def _pick_next_message(
        self,
        db: Session,
        accounts_with_sending: set,
    ) -> EmailMessage | None:
        now = datetime.now(UTC)
        stmt = (
            select(EmailMessage)
            .join(Campaign, Campaign.id == EmailMessage.campaign_id)
            .join(EmailAccount, EmailAccount.id == EmailMessage.email_account_id)
            .where(
                EmailMessage.status == EmailMessageStatus.QUEUED.value,
                Campaign.status == CampaignStatus.RUNNING.value,
                EmailAccount.is_active.is_(True),
                EmailAccount.connection_status == ConnectionStatus.CONNECTED.value,
                EmailMessage.next_attempt_at <= now,
            )
            .order_by(EmailMessage.next_attempt_at.asc(), EmailMessage.created_at.asc())
            .limit(50)
        )
        candidates = list(db.scalars(stmt).all())
        for message in candidates:
            if message.email_account_id in accounts_with_sending:
                continue
            account = db.get(EmailAccount, message.email_account_id)
            if account and account.next_send_allowed_at and account.next_send_allowed_at > now:
                continue
            campaign = db.get(Campaign, message.campaign_id)
            if not campaign or campaign.status != CampaignStatus.RUNNING.value:
                continue
            if account:
                blocked_until = RateLimitService(db, self.settings).limits_block_send(
                    campaign, account, now=now
                )
                if blocked_until and blocked_until > now:
                    message.next_attempt_at = blocked_until
                    continue
            return message
        return None

    def _claim_message(self, db: Session, message: EmailMessage) -> bool:
        now = datetime.now(UTC)
        rfc = message.rfc_message_id or CampaignDeliveryService.assign_rfc_message_id(message)
        result = db.execute(
            update(EmailMessage)
            .where(
                EmailMessage.id == message.id,
                EmailMessage.status == EmailMessageStatus.QUEUED.value,
            )
            .values(
                status=EmailMessageStatus.SENDING.value,
                attempt_count=EmailMessage.attempt_count + 1,
                last_attempt_at=now,
                rfc_message_id=rfc,
            )
        )
        if result.rowcount != 1:
            return False
        db.refresh(message)
        return True

    def _process_claimed_message(
        self,
        db: Session,
        message: EmailMessage,
        rate_limits: RateLimitService,
    ) -> None:
        now = datetime.now(UTC)
        campaign = db.scalar(
            select(Campaign)
            .options(joinedload(Campaign.email_account))
            .where(Campaign.id == message.campaign_id)
        )
        account = campaign.email_account if campaign else None
        recipient = db.get(CampaignRecipient, message.campaign_recipient_id)
        contact = db.get(Contact, message.contact_id)

        if not campaign or campaign.status != CampaignStatus.RUNNING.value:
            self._cancel_message(db, message, "Campaign is not running.")
            return

        if not account or not account.is_active:
            self._fail_message(db, message, "AUTH_EXPIRED", "Email account is inactive.", retryable=False)
            return

        if account.connection_status != ConnectionStatus.CONNECTED.value:
            self._fail_message(db, message, "AUTH_EXPIRED", "Email account is disconnected.", retryable=False)
            return

        if contact and CampaignDeliveryService.contact_no_longer_eligible(contact):
            self._cancel_message(db, message, "Recipient is no longer eligible.")
            if recipient:
                recipient.status = CampaignRecipientStatus.SUPPRESSED.value
                recipient.exclusion_reason = "Recipient no longer eligible at send time"
            message.error_code = "RECIPIENT_NO_LONGER_ELIGIBLE"
            return

        from app.services.suppression_service import SuppressionService

        if SuppressionService(db).is_suppressed(campaign.user_id, message.to_email):
            self._cancel_message(db, message, "Recipient is suppressed.")
            if recipient:
                recipient.status = CampaignRecipientStatus.SUPPRESSED.value
                recipient.exclusion_reason = "Suppressed"
            message.error_code = "SUPPRESSED"
            return

        allowlist = self.settings.campaign_test_allowlist_emails
        if allowlist and message.to_email.lower() not in allowlist:
            self._defer_message(
                db,
                message,
                "TEST_RECIPIENT_NOT_ALLOWED",
                "Recipient is not on the test allowlist.",
                delay_seconds=3600,
            )
            return

        blocked_until = rate_limits.limits_block_send(campaign, account, now=now)
        if blocked_until and blocked_until > now:
            message.status = EmailMessageStatus.QUEUED.value
            message.next_attempt_at = blocked_until
            return

        try:
            subject_tpl = campaign.snapshot_subject or message.subject
            html_tpl = campaign.snapshot_html or message.rendered_html
            text_tpl = campaign.snapshot_plain_text or message.rendered_text

            context = RenderContext(
                first_name=contact.first_name if contact else None,
                last_name=contact.last_name if contact else None,
                company=contact.company if contact else None,
                email=contact.email if contact else message.to_email,
                phone=contact.phone if contact else None,
                website=contact.website if contact else None,
                metadata=contact.contact_metadata if contact else {},
            )
            rendered = self.renderer.render(
                subject=subject_tpl,
                html_content=html_tpl,
                plain_text_content=text_tpl,
                context=context,
            )
            subject = rendered.rendered_subject
            html = sanitize_email_html(rendered.rendered_html)
            text = rendered.rendered_text or html_to_plain_text(html)

            from app.models.user import User
            from app.services.unsubscribe_service import UnsubscribeService

            user = db.get(User, campaign.user_id)
            if not user:
                self._fail_message(
                    db, message, "UNKNOWN", "Campaign owner not found.", retryable=False
                )
                return

            unsub = UnsubscribeService(db)
            html = html + unsub.footer_html(user=user, message=message)
            text = (text or "") + "\n\n" + unsub.footer_text(user=user, message=message)

            message.subject = subject
            message.rendered_html = html
            message.rendered_text = text
            db.flush()

            builder = EmailMessageBuilder(db)
            built = builder.build(
                user=user,
                from_email=account.email_address,
                from_name=account.display_name,
                to_email=message.to_email,
                subject=subject,
                html_body=html,
                text_body=text,
            )
            built.message_id = message.rfc_message_id

            token = EmailAccountService(db)._get_valid_access_token(account)
            result = self.gmail.send_raw_message(token, built.to_mime_bytes())

            message.status = EmailMessageStatus.SENT.value
            message.sent_at = datetime.now(UTC)
            message.provider_message_id = result.provider_message_id
            message.provider_thread_id = result.provider_thread_id
            message.error_code = None
            message.error_message = None
            if recipient:
                recipient.status = CampaignRecipientStatus.SENT.value

            limits = effective_limits(campaign, account)
            account.next_send_allowed_at = datetime.now(UTC) + timedelta(
                seconds=limits.minimum_delay_seconds
            )
            campaign.last_activity_at = datetime.now(UTC)
            worker_state.last_send_success_at = datetime.now(UTC)

            logger.info(
                "campaign.message_sent",
                campaign_id=str(campaign.id),
                message_id=str(message.id),
                email_account_id=str(account.id),
                attempt_count=message.attempt_count,
            )
        except OAuthError as exc:
            account.connection_status = ConnectionStatus.EXPIRED.value
            account.last_connection_error = exc.message
            campaign.status = CampaignStatus.PAUSED.value
            campaign.paused_at = datetime.now(UTC)
            self._release_to_queue_or_fail(
                db, message, classify_exception(exc), recipient
            )
        except (ValidationAppError, Exception) as exc:  # noqa: BLE001
            info = classify_exception(exc)
            logger.warning(
                "campaign.message_send_error",
                message_id=str(message.id),
                campaign_id=str(message.campaign_id),
                error_type=type(exc).__name__,
                error_code=info.code,
                retryable=info.retryable,
            )
            self._release_to_queue_or_fail(db, message, info, recipient)

    def _release_to_queue_or_fail(self, db, message, info, recipient) -> None:
        if info.retryable and message.attempt_count < message.max_attempts:
            delay = retry_delay_seconds(message.attempt_count, self.settings)
            message.status = EmailMessageStatus.QUEUED.value
            message.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay)
            message.error_code = info.code
            message.error_message = info.message
            logger.warning(
                "campaign.message_retry_scheduled",
                message_id=str(message.id),
                error_code=info.code,
                attempt_count=message.attempt_count,
            )
            return
        self._fail_message(db, message, info.code, info.message, retryable=False, recipient=recipient)

    def _fail_message(
        self,
        db,
        message,
        code: str,
        msg: str,
        *,
        retryable: bool,
        recipient=None,
    ) -> None:
        message.status = EmailMessageStatus.FAILED.value
        message.failed_at = datetime.now(UTC)
        message.error_code = code
        message.error_message = msg
        if recipient:
            recipient.status = CampaignRecipientStatus.FAILED.value
        logger.warning(
            "campaign.message_failed",
            message_id=str(message.id),
            error_code=code,
            attempt_count=message.attempt_count,
        )

    def _cancel_message(self, db, message, reason: str) -> None:
        message.status = EmailMessageStatus.CANCELLED.value
        message.error_message = reason
        message.error_code = "CAMPAIGN_CANCELLED"

    def _defer_message(self, db, message, code, msg, delay_seconds: int) -> None:
        message.status = EmailMessageStatus.QUEUED.value
        message.next_attempt_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)
        message.error_code = code
        message.error_message = msg

    def _recover_stale_sending(self, db: Session) -> None:
        threshold = datetime.now(UTC) - timedelta(
            minutes=self.settings.campaign_stale_sending_minutes
        )
        stale = list(
            db.scalars(
                select(EmailMessage).where(
                    EmailMessage.status == EmailMessageStatus.SENDING.value,
                    EmailMessage.last_attempt_at <= threshold,
                )
            ).all()
        )
        for message in stale:
            message.status = EmailMessageStatus.FAILED.value
            message.failed_at = datetime.now(UTC)
            message.error_code = "UNCERTAIN_PROVIDER_RESULT"
            message.error_message = (
                "Send result could not be confirmed after worker interruption."
            )
            recipient = db.get(CampaignRecipient, message.campaign_recipient_id)
            if recipient and recipient.status == CampaignRecipientStatus.QUEUED.value:
                recipient.status = CampaignRecipientStatus.FAILED.value
            logger.warning(
                "campaign.stale_sending_recovered",
                message_id=str(message.id),
                campaign_id=str(message.campaign_id),
            )

    def _check_completions(self, db: Session) -> None:
        running = list(
            db.scalars(
                select(Campaign).where(Campaign.status == CampaignStatus.RUNNING.value)
            ).all()
        )
        for campaign in running:
            actionable = db.scalar(
                select(func.count())
                .select_from(EmailMessage)
                .where(
                    EmailMessage.campaign_id == campaign.id,
                    EmailMessage.status.in_(
                        [
                            EmailMessageStatus.QUEUED.value,
                            EmailMessageStatus.SENDING.value,
                        ]
                    ),
                )
            ) or 0
            if actionable == 0:
                campaign.status = CampaignStatus.COMPLETED.value
                campaign.completed_at = datetime.now(UTC)
                campaign.last_activity_at = datetime.now(UTC)
                logger.info("campaign.completed", campaign_id=str(campaign.id))
