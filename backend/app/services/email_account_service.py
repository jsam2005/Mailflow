"""Email account OAuth, settings, connection tests, and manual test sends."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    OAuthError,
    RateLimitError,
    ValidationAppError,
)
from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.contact_list import ContactList
from app.models.email_account import ConnectionStatus, EmailAccount
from app.models.email_template import EmailTemplate
from app.models.email_test_log import EmailTestLog
from app.models.oauth_state import OAuthState
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
from app.services.email.email_message_builder import EmailMessageBuilder
from app.services.email.gmail_provider import GmailProvider
from app.services.template_render_service import (
    SAMPLE_PREVIEW_CONTEXT,
    RenderContext,
    TemplateRenderService,
)
from app.services.token_encryption_service import TokenEncryptionService, get_token_encryption
from app.utils.email import validate_and_normalize_email
from app.utils.html_sanitize import sanitize_email_html
from app.utils.plain_text import html_to_plain_text

logger = get_logger(__name__)

DEFAULT_TEST_SUBJECT = "MailFlow test email"
DEFAULT_TEST_BODY = "This is a test email sent from MailFlow."
TOKEN_REFRESH_SKEW_SECONDS = 120


class EmailAccountService:
    def __init__(
        self,
        db: Session,
        *,
        encryption: TokenEncryptionService | None = None,
        gmail: GmailProvider | None = None,
    ) -> None:
        self.db = db
        self.settings = get_settings()
        self.encryption = encryption or get_token_encryption()
        self.gmail = gmail or GmailProvider(self.settings)
        self.renderer = TemplateRenderService()
        self.message_builder = EmailMessageBuilder(db)

    # ------------------------------------------------------------------
    # List / get / update
    # ------------------------------------------------------------------

    def list_accounts(self, user: User) -> EmailAccountListResponse:
        rows = list(
            self.db.scalars(
                select(EmailAccount)
                .where(EmailAccount.user_id == user.id)
                .order_by(EmailAccount.created_at.desc())
            ).all()
        )
        return EmailAccountListResponse(items=[self._to_response(a) for a in rows])

    def get_account(self, user: User, account_id: UUID) -> EmailAccountResponse:
        return self._to_response(self._get_owned(user, account_id))

    def update_account(
        self,
        user: User,
        account_id: UUID,
        data: EmailAccountUpdate,
    ) -> EmailAccountResponse:
        account = self._get_owned(user, account_id)
        daily = data.daily_send_limit if data.daily_send_limit is not None else account.daily_send_limit
        hourly = (
            data.hourly_send_limit if data.hourly_send_limit is not None else account.hourly_send_limit
        )
        min_delay = (
            data.minimum_delay_seconds
            if data.minimum_delay_seconds is not None
            else account.minimum_delay_seconds
        )
        max_delay = (
            data.maximum_delay_seconds
            if data.maximum_delay_seconds is not None
            else account.maximum_delay_seconds
        )
        if hourly > daily:
            raise ValidationAppError("Hourly send limit cannot exceed daily send limit.")
        if max_delay < min_delay:
            raise ValidationAppError(
                "Maximum delay must be greater than or equal to minimum delay."
            )
        account.daily_send_limit = daily
        account.hourly_send_limit = hourly
        account.minimum_delay_seconds = min_delay
        account.maximum_delay_seconds = max_delay
        self.db.commit()
        self.db.refresh(account)
        logger.info(
            "email_account.settings_updated",
            user_id=str(user.id),
            email_account_id=str(account.id),
            provider=account.provider,
        )
        return self._to_response(account)

    # ------------------------------------------------------------------
    # OAuth connect / callback / reconnect
    # ------------------------------------------------------------------

    def start_google_connect(self, user: User) -> GoogleConnectResponse:
        state = secrets.token_urlsafe(32)
        state_hash = self._hash_state(state)
        now = datetime.now(UTC)
        record = OAuthState(
            user_id=user.id,
            provider="gmail",
            state_hash=state_hash,
            expires_at=now + timedelta(minutes=self.settings.oauth_state_ttl_minutes),
            used_at=None,
            created_at=now,
        )
        self.db.add(record)
        self.db.commit()
        url = self.gmail.get_authorization_url(state)
        logger.info(
            "oauth.started",
            user_id=str(user.id),
            provider="gmail",
        )
        return GoogleConnectResponse(authorization_url=url)

    def handle_google_callback(
        self,
        *,
        code: str | None,
        state: str | None,
        error: str | None,
    ) -> str:
        frontend = self.settings.frontend_url.rstrip("/")
        success_url = f"{frontend}/email-accounts?connected=1"
        failure_url = f"{frontend}/email-accounts?error=oauth_failed"

        if error:
            logger.warning("oauth.callback_denied", provider="gmail", error=error)
            return failure_url
        if not code or not state:
            logger.warning("oauth.callback_missing_params", provider="gmail")
            return failure_url

        try:
            oauth_state = self._consume_oauth_state(state, provider="gmail")
            tokens = self.gmail.exchange_code(code)
            profile = self.gmail.get_profile(tokens.access_token)
            account = self._upsert_gmail_account(oauth_state.user_id, profile, tokens)
            logger.info(
                "oauth.callback_success",
                user_id=str(oauth_state.user_id),
                email_account_id=str(account.id),
                provider="gmail",
            )
            logger.info(
                "email_account.connected",
                user_id=str(oauth_state.user_id),
                email_account_id=str(account.id),
                provider="gmail",
            )
            return success_url
        except (OAuthError, ValidationAppError, NotFoundError) as exc:
            logger.warning(
                "oauth.callback_failure",
                provider="gmail",
                error=str(exc.message) if hasattr(exc, "message") else type(exc).__name__,
            )
            return failure_url
        except Exception:  # noqa: BLE001
            logger.exception("oauth.callback_unexpected", provider="gmail")
            return failure_url

    def reconnect(self, user: User, account_id: UUID) -> GoogleConnectResponse:
        account = self._get_owned(user, account_id)
        if account.provider != "gmail":
            raise ValidationAppError("Reconnect is only supported for Gmail accounts.")
        return self.start_google_connect(user)

    # ------------------------------------------------------------------
    # Tokens / connection
    # ------------------------------------------------------------------

    def test_connection(self, user: User, account_id: UUID) -> ConnectionTestResponse:
        account = self._get_owned(user, account_id)
        try:
            access_token = self._get_valid_access_token(account)
            result = self.gmail.test_connection(access_token)
        except OAuthError as exc:
            account.connection_status = ConnectionStatus.EXPIRED.value
            account.last_connection_check_at = datetime.now(UTC)
            account.last_connection_error = exc.message
            self.db.commit()
            logger.info(
                "email_account.connection_test",
                user_id=str(user.id),
                email_account_id=str(account.id),
                provider=account.provider,
                connected=False,
            )
            return ConnectionTestResponse(
                connected=False,
                message=exc.message,
            )

        account.last_connection_check_at = datetime.now(UTC)
        if result.connected:
            account.connection_status = ConnectionStatus.CONNECTED.value
            account.last_connection_error = None
            if result.email_address:
                account.email_address = result.email_address.lower().strip()
        else:
            account.connection_status = (
                ConnectionStatus.EXPIRED.value
                if result.error in {"unauthorized"}
                else ConnectionStatus.ERROR.value
            )
            account.last_connection_error = result.message
        self.db.commit()
        logger.info(
            "email_account.connection_test",
            user_id=str(user.id),
            email_account_id=str(account.id),
            provider=account.provider,
            connected=result.connected,
        )
        return ConnectionTestResponse(
            connected=result.connected,
            email_address=result.email_address or account.email_address,
            message=result.message,
        )

    def disconnect(self, user: User, account_id: UUID) -> None:
        account = self._get_owned(user, account_id)
        refresh = None
        access = None
        try:
            if account.oauth_refresh_token_encrypted:
                refresh = self.encryption.decrypt(account.oauth_refresh_token_encrypted)
            if account.oauth_access_token_encrypted:
                access = self.encryption.decrypt(account.oauth_access_token_encrypted)
        except ValidationAppError:
            refresh = None
            access = None

        for token in (refresh, access):
            if token:
                try:
                    self.gmail.revoke_token(token)
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "email_account.revoke_failed",
                        email_account_id=str(account.id),
                        provider=account.provider,
                    )

        account.oauth_access_token_encrypted = None
        account.oauth_refresh_token_encrypted = None
        account.oauth_token_expiry = None
        account.oauth_scope = None
        account.connection_status = ConnectionStatus.DISCONNECTED.value
        account.is_active = False
        account.last_connection_error = None
        self.db.commit()
        logger.info(
            "email_account.disconnected",
            user_id=str(user.id),
            email_account_id=str(account.id),
            provider=account.provider,
        )

    # ------------------------------------------------------------------
    # Test email
    # ------------------------------------------------------------------

    def send_test_email(
        self,
        user: User,
        account_id: UUID,
        data: SendTestEmailRequest,
    ) -> SendTestEmailResponse:
        account = self._get_owned(user, account_id)
        if account.connection_status == ConnectionStatus.DISCONNECTED.value:
            raise ValidationAppError("This account is disconnected. Reconnect Gmail first.")
        if not account.is_active and account.connection_status != ConnectionStatus.CONNECTED.value:
            raise ValidationAppError("This account is not active. Reconnect Gmail first.")

        self._enforce_test_rate_limit(user, account)

        display_email, _ = validate_and_normalize_email(str(data.to_email))
        subject, html_body, text_body, template_id, contact_id = self._resolve_test_content(
            user, data
        )

        now = datetime.now(UTC)
        log = EmailTestLog(
            user_id=user.id,
            email_account_id=account.id,
            template_id=template_id,
            contact_id=contact_id,
            to_email=display_email,
            subject=subject[:255],
            status="failed",
            created_at=now,
        )
        self.db.add(log)
        self.db.flush()

        try:
            access_token = self._get_valid_access_token(account)
            built = self.message_builder.build(
                user=user,
                from_email=account.email_address,
                from_name=account.display_name,
                to_email=display_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
            )
            result = self.gmail.send_raw_message(access_token, built.to_mime_bytes())
            log.status = "sent"
            log.sent_at = datetime.now(UTC)
            log.provider_message_id = result.provider_message_id
            log.provider_thread_id = result.provider_thread_id
            account.sent_today = (account.sent_today or 0) + 1
            account.sent_current_hour = (account.sent_current_hour or 0) + 1
            self.db.commit()
            logger.info(
                "email_account.test_email_sent",
                user_id=str(user.id),
                email_account_id=str(account.id),
                provider=account.provider,
            )
            return SendTestEmailResponse(
                sent=True,
                to_email=display_email,
                subject=subject,
                provider_message_id=result.provider_message_id,
                thread_id=result.provider_thread_id,
                timestamp=log.sent_at or datetime.now(UTC),
                message="Test email sent successfully.",
            )
        except (OAuthError, ValidationAppError, NotFoundError) as exc:
            message = exc.message if hasattr(exc, "message") else str(exc)
            log.error_message = message
            self.db.commit()
            logger.warning(
                "email_account.test_email_failed",
                user_id=str(user.id),
                email_account_id=str(account.id),
                provider=account.provider,
            )
            if isinstance(exc, OAuthError):
                account.connection_status = ConnectionStatus.EXPIRED.value
                account.last_connection_error = message
                self.db.commit()
            raise
        except Exception as exc:  # noqa: BLE001
            log.error_message = "Test email failed."
            self.db.commit()
            logger.exception(
                "email_account.test_email_failed",
                user_id=str(user.id),
                email_account_id=str(account.id),
                provider=account.provider,
            )
            raise ValidationAppError("Test email failed. Please try again.") from exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_test_content(
        self,
        user: User,
        data: SendTestEmailRequest,
    ) -> tuple[str, str, str, UUID | None, UUID | None]:
        if data.mode == "template":
            if not data.template_id:
                raise ValidationAppError("template_id is required for template mode.")
            template = self.db.scalar(
                select(EmailTemplate).where(
                    EmailTemplate.id == data.template_id,
                    EmailTemplate.user_id == user.id,
                )
            )
            if not template:
                raise NotFoundError("Template not found.")

            context = SAMPLE_PREVIEW_CONTEXT
            contact_id = None
            if data.contact_id:
                contact = self.db.scalar(
                    select(Contact)
                    .join(ContactList, Contact.contact_list_id == ContactList.id)
                    .where(
                        Contact.id == data.contact_id,
                        ContactList.user_id == user.id,
                    )
                )
                if not contact:
                    raise NotFoundError("Contact not found.")
                contact_id = contact.id
                context = RenderContext(
                    first_name=contact.first_name,
                    last_name=contact.last_name,
                    company=contact.company,
                    email=contact.email,
                    phone=contact.phone,
                    website=contact.website,
                    metadata=contact.contact_metadata or {},
                )

            rendered = self.renderer.render(
                subject=template.subject,
                html_content=template.html_content,
                plain_text_content=template.plain_text_content,
                context=context,
            )
            html = sanitize_email_html(rendered.rendered_html)
            text = rendered.rendered_text or html_to_plain_text(html)
            return rendered.rendered_subject, html, text, template.id, contact_id

        subject = (data.subject or DEFAULT_TEST_SUBJECT).strip() or DEFAULT_TEST_SUBJECT
        message = (data.message or DEFAULT_TEST_BODY).strip() or DEFAULT_TEST_BODY
        # Allow simple HTML from the textarea; sanitize first.
        if "<" in message and ">" in message:
            html = sanitize_email_html(message)
            text = html_to_plain_text(html)
        else:
            safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html = f"<p>{safe}</p>"
            text = message
        return subject, html, text, None, None

    def _enforce_test_rate_limit(self, user: User, account: EmailAccount) -> None:
        since = datetime.now(UTC) - timedelta(hours=1)
        count = self.db.scalar(
            select(func.count())
            .select_from(EmailTestLog)
            .where(
                EmailTestLog.user_id == user.id,
                EmailTestLog.email_account_id == account.id,
                EmailTestLog.status == "sent",
                EmailTestLog.created_at >= since,
            )
        )
        limit = self.settings.test_email_hourly_limit
        if (count or 0) >= limit:
            raise RateLimitError(
                f"Test email limit reached ({limit} per hour for this account). Try again later."
            )

    def _get_valid_access_token(self, account: EmailAccount) -> str:
        if not account.oauth_access_token_encrypted and not account.oauth_refresh_token_encrypted:
            account.connection_status = ConnectionStatus.DISCONNECTED.value
            self.db.commit()
            raise OAuthError("This account is disconnected. Reconnect Gmail.")

        needs_refresh = True
        if account.oauth_access_token_encrypted and account.oauth_token_expiry:
            expiry = account.oauth_token_expiry
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=UTC)
            needs_refresh = expiry <= datetime.now(UTC) + timedelta(seconds=TOKEN_REFRESH_SKEW_SECONDS)

        if not needs_refresh and account.oauth_access_token_encrypted:
            return self.encryption.decrypt(account.oauth_access_token_encrypted)

        if not account.oauth_refresh_token_encrypted:
            account.connection_status = ConnectionStatus.EXPIRED.value
            account.last_connection_error = "Google authorization has expired. Reconnect this account."
            self.db.commit()
            raise OAuthError("Google authorization has expired. Reconnect this account.")

        refresh_token = self.encryption.decrypt(account.oauth_refresh_token_encrypted)
        try:
            tokens = self.gmail.refresh_access_token(refresh_token)
        except OAuthError as exc:
            account.connection_status = ConnectionStatus.EXPIRED.value
            account.last_connection_error = exc.message
            self.db.commit()
            logger.warning(
                "email_account.token_refresh_failed",
                email_account_id=str(account.id),
                provider=account.provider,
            )
            raise

        account.oauth_access_token_encrypted = self.encryption.encrypt(tokens.access_token)
        if tokens.refresh_token:
            account.oauth_refresh_token_encrypted = self.encryption.encrypt(tokens.refresh_token)
        account.oauth_token_expiry = tokens.expires_at
        if tokens.scope:
            account.oauth_scope = (
                tokens.scope.split() if isinstance(tokens.scope, str) else tokens.scope
            )
        account.connection_status = ConnectionStatus.CONNECTED.value
        account.last_connection_error = None
        self.db.commit()
        logger.info(
            "email_account.token_refresh_success",
            email_account_id=str(account.id),
            provider=account.provider,
        )
        return tokens.access_token

    def _upsert_gmail_account(self, user_id: UUID, profile, tokens) -> EmailAccount:
        email_address = profile.email_address.lower().strip()
        existing = self.db.scalar(
            select(EmailAccount).where(
                EmailAccount.user_id == user_id,
                EmailAccount.provider == "gmail",
                EmailAccount.email_address == email_address,
            )
        )
        scope = tokens.scope
        if isinstance(scope, str):
            scope = scope.split()

        access_enc = self.encryption.encrypt(tokens.access_token)
        refresh_enc = (
            self.encryption.encrypt(tokens.refresh_token) if tokens.refresh_token else None
        )

        if existing:
            if (
                existing.connection_status == ConnectionStatus.CONNECTED.value
                and existing.is_active
                and existing.oauth_refresh_token_encrypted
            ):
                # Already connected with tokens — still allow reconnect update
                pass
            existing.display_name = profile.display_name or existing.display_name
            existing.provider_account_id = profile.provider_account_id
            existing.oauth_access_token_encrypted = access_enc
            if refresh_enc:
                existing.oauth_refresh_token_encrypted = refresh_enc
            existing.oauth_token_expiry = tokens.expires_at
            existing.oauth_scope = scope
            existing.connection_status = ConnectionStatus.CONNECTED.value
            existing.last_connection_error = None
            existing.last_connection_check_at = datetime.now(UTC)
            existing.is_active = True
            self.db.commit()
            self.db.refresh(existing)
            return existing

        account = EmailAccount(
            user_id=user_id,
            provider="gmail",
            email_address=email_address,
            display_name=profile.display_name,
            provider_account_id=profile.provider_account_id,
            oauth_access_token_encrypted=access_enc,
            oauth_refresh_token_encrypted=refresh_enc,
            oauth_token_expiry=tokens.expires_at,
            oauth_scope=scope,
            daily_send_limit=self.settings.default_daily_send_limit,
            hourly_send_limit=self.settings.default_hourly_send_limit,
            minimum_delay_seconds=self.settings.default_min_delay_seconds,
            maximum_delay_seconds=self.settings.default_max_delay_seconds,
            sent_today=0,
            sent_current_hour=0,
            connection_status=ConnectionStatus.CONNECTED.value,
            last_connection_check_at=datetime.now(UTC),
            last_connection_error=None,
            is_active=True,
        )
        self.db.add(account)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise ConflictError(
                "This Gmail account is already connected to your MailFlow workspace."
            ) from exc
        self.db.refresh(account)
        return account

    def _consume_oauth_state(self, state: str, *, provider: str) -> OAuthState:
        state_hash = self._hash_state(state)
        record = self.db.scalar(
            select(OAuthState).where(
                OAuthState.state_hash == state_hash,
                OAuthState.provider == provider,
            )
        )
        if not record:
            raise OAuthError("Invalid OAuth state.")
        now = datetime.now(UTC)
        expires = record.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if record.used_at is not None:
            raise OAuthError("OAuth state has already been used.")
        if expires < now:
            raise OAuthError("OAuth state has expired.")
        record.used_at = now
        self.db.commit()
        self.db.refresh(record)
        return record

    @staticmethod
    def _hash_state(state: str) -> str:
        return hashlib.sha256(state.encode("utf-8")).hexdigest()

    def _get_owned(self, user: User, account_id: UUID) -> EmailAccount:
        account = self.db.scalar(
            select(EmailAccount).where(
                EmailAccount.id == account_id,
                EmailAccount.user_id == user.id,
            )
        )
        if not account:
            raise NotFoundError("Email account not found.")
        return account

    @staticmethod
    def _to_response(account: EmailAccount) -> EmailAccountResponse:
        return EmailAccountResponse(
            id=account.id,
            provider=account.provider,
            email_address=account.email_address,
            display_name=account.display_name,
            daily_send_limit=account.daily_send_limit,
            hourly_send_limit=account.hourly_send_limit,
            minimum_delay_seconds=account.minimum_delay_seconds,
            maximum_delay_seconds=account.maximum_delay_seconds,
            sent_today=account.sent_today,
            connection_status=account.connection_status,
            last_connection_check_at=account.last_connection_check_at,
            last_connection_error=account.last_connection_error,
            is_active=account.is_active,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )
