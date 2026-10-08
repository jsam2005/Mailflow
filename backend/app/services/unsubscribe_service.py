"""Signed unsubscribe tokens and public unsubscribe flow."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.models.email_message import EmailMessage
from app.models.suppression import SuppressionReason
from app.models.user import User
from app.services.suppression_service import SuppressionService, normalize_email

logger = get_logger(__name__)


class UnsubscribeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self._serializer = URLSafeTimedSerializer(
            secret_key=self.settings.jwt_secret,
            salt="mailflow-unsubscribe-v1",
        )

    def make_token(
        self,
        *,
        user_id: UUID,
        email: str,
        message_id: UUID | None = None,
        campaign_id: UUID | None = None,
    ) -> str:
        payload = {
            "u": str(user_id),
            "e": normalize_email(email),
            "m": str(message_id) if message_id else None,
            "c": str(campaign_id) if campaign_id else None,
        }
        return self._serializer.dumps(payload)

    def unsubscribe_url(self, token: str) -> str:
        base = self.settings.effective_unsubscribe_base_url
        return f"{base}/unsubscribe/{token}"

    def verify_token(self, token: str) -> dict:
        max_age = self.settings.unsubscribe_token_ttl_days * 24 * 3600
        try:
            data = self._serializer.loads(token, max_age=max_age)
        except SignatureExpired as exc:
            raise ValidationAppError("This unsubscribe link has expired.") from exc
        except BadSignature as exc:
            raise ValidationAppError("Invalid unsubscribe link.") from exc
        if not data.get("u") or not data.get("e"):
            raise ValidationAppError("Invalid unsubscribe link.")
        return data

    def confirm(self, token: str) -> dict:
        data = self.verify_token(token)
        user = self.db.get(User, UUID(data["u"]))
        if not user:
            raise NotFoundError("Unsubscribe target not found.")
        email = data["e"]
        service = SuppressionService(self.db)
        if not service.is_suppressed(user.id, email):
            service.suppress(
                user,
                email,
                reason=SuppressionReason.UNSUBSCRIBE.value,
                source="unsubscribe_link",
                cancel_queued=True,
            )
        else:
            # still cancel any remaining queued
            service._cancel_queued_for_email(user.id, normalize_email(email))
            self.db.commit()
        logger.info("unsubscribe.confirmed", user_id=str(user.id))
        return {"status": "unsubscribed", "email": email}

    def footer_html(self, *, user: User, message: EmailMessage) -> str:
        token = self.make_token(
            user_id=user.id,
            email=message.to_email,
            message_id=message.id,
            campaign_id=message.campaign_id,
        )
        url = self.unsubscribe_url(token)
        business = self.settings.business_name or "MailFlow"
        address = self.settings.business_address
        support = self.settings.support_email
        parts = [
            f'<p style="font-size:12px;color:#666;margin-top:24px;">',
            f"You received this email from {business}.",
        ]
        if address:
            parts.append(f"<br/>{address}")
        if support:
            parts.append(f"<br/>Contact: {support}")
        parts.append(f'<br/><a href="{url}">Unsubscribe</a></p>')
        return "".join(parts)

    def footer_text(self, *, user: User, message: EmailMessage) -> str:
        token = self.make_token(
            user_id=user.id,
            email=message.to_email,
            message_id=message.id,
            campaign_id=message.campaign_id,
        )
        url = self.unsubscribe_url(token)
        business = self.settings.business_name or "MailFlow"
        lines = [f"You received this email from {business}.", f"Unsubscribe: {url}"]
        if self.settings.business_address:
            lines.insert(1, self.settings.business_address)
        return "\n".join(lines)
