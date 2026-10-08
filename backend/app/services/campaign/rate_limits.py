"""Campaign and account send rate limit checks."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.campaign import Campaign
from app.models.email_account import EmailAccount
from app.models.email_message import EmailMessage, EmailMessageStatus
from app.schemas.campaigns import EffectiveLimits


def effective_limits(campaign: Campaign, account: EmailAccount) -> EffectiveLimits:
    daily = min(
        campaign.daily_limit if campaign.daily_limit is not None else account.daily_send_limit,
        account.daily_send_limit,
    )
    hourly = min(
        campaign.hourly_limit if campaign.hourly_limit is not None else account.hourly_send_limit,
        account.hourly_send_limit,
    )
    min_delay = (
        campaign.minimum_delay_seconds
        if campaign.minimum_delay_seconds is not None
        else account.minimum_delay_seconds
    )
    max_delay = (
        campaign.maximum_delay_seconds
        if campaign.maximum_delay_seconds is not None
        else account.maximum_delay_seconds
    )
    inherited = (
        campaign.daily_limit is None
        and campaign.hourly_limit is None
        and campaign.minimum_delay_seconds is None
        and campaign.maximum_delay_seconds is None
    )
    return EffectiveLimits(
        daily_limit=daily,
        hourly_limit=hourly,
        minimum_delay_seconds=min_delay,
        maximum_delay_seconds=max_delay,
        inherited_from_account=inherited,
    )


def _day_start_utc(now: datetime, tz_name: str) -> datetime:
    tz = ZoneInfo(tz_name)
    local = now.astimezone(tz)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(UTC)


class RateLimitService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self.db = db
        self.settings = settings

    def account_daily_sent(self, account_id, *, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        day_start = _day_start_utc(now, self.settings.app_timezone)
        return (
            self.db.scalar(
                select(func.count())
                .select_from(EmailMessage)
                .where(
                    EmailMessage.email_account_id == account_id,
                    EmailMessage.status == EmailMessageStatus.SENT.value,
                    EmailMessage.sent_at >= day_start,
                )
            )
            or 0
        )

    def account_hourly_sent(self, account_id, *, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        since = now - timedelta(hours=1)
        return (
            self.db.scalar(
                select(func.count())
                .select_from(EmailMessage)
                .where(
                    EmailMessage.email_account_id == account_id,
                    EmailMessage.status == EmailMessageStatus.SENT.value,
                    EmailMessage.sent_at >= since,
                )
            )
            or 0
        )

    def campaign_daily_sent(self, campaign_id, *, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        day_start = _day_start_utc(now, self.settings.app_timezone)
        return (
            self.db.scalar(
                select(func.count())
                .select_from(EmailMessage)
                .where(
                    EmailMessage.campaign_id == campaign_id,
                    EmailMessage.status == EmailMessageStatus.SENT.value,
                    EmailMessage.sent_at >= day_start,
                )
            )
            or 0
        )

    def campaign_hourly_sent(self, campaign_id, *, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        since = now - timedelta(hours=1)
        return (
            self.db.scalar(
                select(func.count())
                .select_from(EmailMessage)
                .where(
                    EmailMessage.campaign_id == campaign_id,
                    EmailMessage.status == EmailMessageStatus.SENT.value,
                    EmailMessage.sent_at >= since,
                )
            )
            or 0
        )

    def limits_block_send(
        self,
        campaign: Campaign,
        account: EmailAccount,
        *,
        now: datetime | None = None,
    ) -> datetime | None:
        """Return earliest time sending may resume, or None if allowed now."""
        now = now or datetime.now(UTC)
        limits = effective_limits(campaign, account)

        if account.next_send_allowed_at and account.next_send_allowed_at > now:
            return account.next_send_allowed_at

        if self.account_daily_sent(account.id, now=now) >= limits.daily_limit:
            day_start = _day_start_utc(now, self.settings.app_timezone)
            return day_start + timedelta(days=1)

        if self.account_hourly_sent(account.id, now=now) >= limits.hourly_limit:
            return now + timedelta(hours=1)

        if self.campaign_daily_sent(campaign.id, now=now) >= limits.daily_limit:
            day_start = _day_start_utc(now, self.settings.app_timezone)
            return day_start + timedelta(days=1)

        if self.campaign_hourly_sent(campaign.id, now=now) >= limits.hourly_limit:
            return now + timedelta(hours=1)

        return None
