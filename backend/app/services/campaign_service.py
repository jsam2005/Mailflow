"""Campaign planning: drafts, recipient snapshots, validation, ready (no sending)."""

from __future__ import annotations

from datetime import UTC, datetime
from math import ceil
from uuid import UUID

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.models.campaign import Campaign, CampaignStatus
from app.models.campaign_recipient import CampaignRecipient, CampaignRecipientStatus
from app.models.contact import Contact, ContactStatus
from app.models.contact_list import ContactList
from app.models.email_account import ConnectionStatus, EmailAccount
from app.models.email_template import EmailTemplate
from app.models.user import User
from app.schemas.campaigns import (
    AccountSummary,
    CampaignCreate,
    CampaignListResponse,
    CampaignPreviewRequest,
    CampaignPreviewResponse,
    CampaignResponse,
    CampaignReviewResponse,
    CampaignStatsResponse,
    CampaignUpdate,
    CampaignValidationResponse,
    ContactListSummary,
    EffectiveLimits,
    PaginatedRecipientsResponse,
    CampaignRecipientResponse,
    RecipientSnapshotRequest,
    RecipientSnapshotResponse,
    TemplateSummary,
)
from app.services.template_render_service import (
    VARIABLE_PATTERN,
    RenderContext,
    TemplateRenderService,
)
from app.utils.html_sanitize import sanitize_email_html
from app.utils.plain_text import html_to_plain_text

logger = get_logger(__name__)

SORT_COLUMNS = {
    "created_at": Campaign.created_at,
    "updated_at": Campaign.updated_at,
    "name": Campaign.name,
    "status": Campaign.status,
}

BATCH_SIZE = 500

EXCLUDED_STATUSES = {
    ContactStatus.INVALID: (
        CampaignRecipientStatus.INVALID.value,
        "Contact status is invalid",
    ),
    ContactStatus.UNSUBSCRIBED: (
        CampaignRecipientStatus.SUPPRESSED.value,
        "Contact is unsubscribed",
    ),
    ContactStatus.SUPPRESSED: (
        CampaignRecipientStatus.SUPPRESSED.value,
        "Contact is suppressed",
    ),
    ContactStatus.BOUNCED: (
        CampaignRecipientStatus.SUPPRESSED.value,
        "Contact previously bounced",
    ),
}


class CampaignService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.renderer = TemplateRenderService()

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, user: User, data: CampaignCreate) -> CampaignResponse:
        campaign = Campaign(
            user_id=user.id,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            status=CampaignStatus.DRAFT.value,
            stop_on_reply=True,
            skip_suppressed=True,
        )
        self.db.add(campaign)
        self.db.commit()
        self.db.refresh(campaign)
        logger.info("campaign.created", user_id=str(user.id), campaign_id=str(campaign.id))
        return self._to_response(campaign, include_relations=True)

    def list_campaigns(
        self,
        user: User,
        *,
        page: int = 1,
        page_size: int = 25,
        search: str | None = None,
        status: str | None = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> CampaignListResponse:
        filters = [Campaign.user_id == user.id]
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(Campaign.name.ilike(term), Campaign.description.ilike(term))
            )
        if status:
            filters.append(Campaign.status == status.strip().lower())

        from sqlalchemy import and_

        where_clause = and_(*filters)
        total = self.db.scalar(
            select(func.count()).select_from(Campaign).where(where_clause)
        ) or 0
        column = SORT_COLUMNS.get(sort_by, Campaign.updated_at)
        order = column.asc() if sort_order == "asc" else column.desc()
        items = list(
            self.db.scalars(
                select(Campaign)
                .options(
                    joinedload(Campaign.email_account),
                    joinedload(Campaign.template),
                    joinedload(Campaign.contact_list),
                )
                .where(where_clause)
                .order_by(order, Campaign.id.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).unique().all()
        )
        return CampaignListResponse(
            items=[self._to_response(c, include_relations=True, include_stats=True) for c in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get(self, user: User, campaign_id: UUID) -> CampaignResponse:
        campaign = self._get_owned(user, campaign_id, load_relations=True)
        return self._to_response(campaign, include_relations=True, include_stats=True)

    def update(
        self,
        user: User,
        campaign_id: UUID,
        data: CampaignUpdate,
    ) -> CampaignResponse:
        campaign = self._get_owned(user, campaign_id, load_relations=True)
        if campaign.status == CampaignStatus.CANCELLED.value:
            raise ValidationAppError("Cancelled campaigns cannot be edited.")
        if campaign.status == CampaignStatus.READY.value:
            raise ValidationAppError(
                "Ready campaigns cannot be edited directly. Return to draft first."
            )
        if campaign.status != CampaignStatus.DRAFT.value:
            raise ValidationAppError("Only draft campaigns can be edited.")

        if data.name is not None:
            campaign.name = data.name.strip()
        if data.description is not None:
            campaign.description = data.description.strip() or None

        if data.email_account_id is not None:
            account = self._get_owned_account(user, data.email_account_id)
            campaign.email_account_id = account.id

        if data.template_id is not None:
            template = self._get_owned_template(user, data.template_id)
            campaign.template_id = template.id

        if data.contact_list_id is not None:
            contact_list = self._get_owned_list(user, data.contact_list_id)
            campaign.contact_list_id = contact_list.id

        if data.clear_overrides:
            campaign.subject_override = None
            campaign.html_override = None
            campaign.plain_text_override = None
        else:
            if data.subject_override is not None:
                campaign.subject_override = data.subject_override.strip() or None
            if data.html_override is not None:
                campaign.html_override = sanitize_email_html(data.html_override)
            if data.plain_text_override is not None:
                campaign.plain_text_override = data.plain_text_override

        if data.use_custom_content is True and data.html_override is None and campaign.template_id:
            # Copy template into overrides without mutating template
            template = self._get_owned_template(user, campaign.template_id)
            campaign.subject_override = campaign.subject_override or template.subject
            campaign.html_override = campaign.html_override or sanitize_email_html(
                template.html_content
            )
            campaign.plain_text_override = (
                campaign.plain_text_override or template.plain_text_content
            )

        self._apply_limit_updates(campaign, data, user)

        if data.stop_on_reply is not None:
            campaign.stop_on_reply = data.stop_on_reply
        if data.skip_suppressed is not None:
            campaign.skip_suppressed = data.skip_suppressed

        # Editing draft clears any stale snapshot
        campaign.snapshot_subject = None
        campaign.snapshot_html = None
        campaign.snapshot_plain_text = None
        campaign.ready_at = None

        self.db.commit()
        self.db.refresh(campaign)
        campaign = self._get_owned(user, campaign.id, load_relations=True)
        logger.info(
            "campaign.updated",
            user_id=str(user.id),
            campaign_id=str(campaign.id),
        )
        return self._to_response(campaign, include_relations=True, include_stats=True)

    def delete_draft(self, user: User, campaign_id: UUID) -> None:
        campaign = self._get_owned(user, campaign_id)
        if campaign.status != CampaignStatus.DRAFT.value:
            raise ValidationAppError("Only draft campaigns can be deleted. Cancel ready campaigns instead.")
        self.db.delete(campaign)
        self.db.commit()
        logger.info("campaign.deleted", user_id=str(user.id), campaign_id=str(campaign_id))

    def cancel(self, user: User, campaign_id: UUID) -> CampaignResponse:
        from app.services.campaign_delivery_service import CampaignDeliveryService

        return CampaignDeliveryService(self.db).cancel(user, campaign_id)

    def return_to_draft(self, user: User, campaign_id: UUID) -> CampaignResponse:
        campaign = self._get_owned(user, campaign_id, load_relations=True)
        if campaign.status != CampaignStatus.READY.value:
            raise ValidationAppError("Only ready campaigns can be returned to draft.")
        campaign.status = CampaignStatus.DRAFT.value
        campaign.ready_at = None
        # Keep snapshot as draft overrides so content remains editable baseline
        if campaign.snapshot_subject and not campaign.subject_override:
            campaign.subject_override = campaign.snapshot_subject
        if campaign.snapshot_html and not campaign.html_override:
            campaign.html_override = campaign.snapshot_html
        if campaign.snapshot_plain_text and campaign.plain_text_override is None:
            campaign.plain_text_override = campaign.snapshot_plain_text
        campaign.snapshot_subject = None
        campaign.snapshot_html = None
        campaign.snapshot_plain_text = None
        self.db.commit()
        self.db.refresh(campaign)
        logger.info("campaign.returned_to_draft", user_id=str(user.id), campaign_id=str(campaign.id))
        return self._to_response(campaign, include_relations=True, include_stats=True)

    # ------------------------------------------------------------------
    # Recipients
    # ------------------------------------------------------------------

    def snapshot_recipients(
        self,
        user: User,
        campaign_id: UUID,
        data: RecipientSnapshotRequest,
    ) -> RecipientSnapshotResponse:
        campaign = self._get_owned(user, campaign_id)
        if campaign.status != CampaignStatus.DRAFT.value:
            raise ValidationAppError("Recipients can only be snapshotted for draft campaigns.")

        contact_list = self._get_owned_list(user, data.contact_list_id)

        # Transactional replace: delete then batch insert
        self.db.execute(
            delete(CampaignRecipient).where(CampaignRecipient.campaign_id == campaign.id)
        )

        counts = {
            "total": 0,
            "eligible": 0,
            "invalid": 0,
            "suppressed": 0,
            "excluded": 0,
        }
        batch: list[CampaignRecipient] = []

        stmt = (
            select(Contact)
            .where(Contact.contact_list_id == contact_list.id)
            .order_by(Contact.id.asc())
        )
        for contact in self.db.scalars(stmt).yield_per(BATCH_SIZE):
            counts["total"] += 1
            status, reason = self._classify_contact(contact, campaign.skip_suppressed)
            if status == CampaignRecipientStatus.PENDING.value:
                counts["eligible"] += 1
            elif status == CampaignRecipientStatus.INVALID.value:
                counts["invalid"] += 1
            elif status == CampaignRecipientStatus.SUPPRESSED.value:
                counts["suppressed"] += 1
            else:
                counts["excluded"] += 1

            batch.append(
                CampaignRecipient(
                    campaign_id=campaign.id,
                    contact_id=contact.id,
                    status=status,
                    exclusion_reason=reason,
                )
            )
            if len(batch) >= BATCH_SIZE:
                self.db.add_all(batch)
                self.db.flush()
                batch.clear()

        if batch:
            self.db.add_all(batch)

        campaign.contact_list_id = contact_list.id
        self.db.commit()

        stats = self.get_stats(user, campaign.id)
        logger.info(
            "campaign.recipients_snapshotted",
            user_id=str(user.id),
            campaign_id=str(campaign.id),
            total=counts["total"],
            eligible=counts["eligible"],
        )
        return RecipientSnapshotResponse(
            contact_list_id=contact_list.id,
            total=counts["total"],
            eligible=counts["eligible"],
            invalid=counts["invalid"],
            suppressed=counts["suppressed"],
            excluded=counts["excluded"],
            stats=stats,
        )

    def get_stats(self, user: User, campaign_id: UUID) -> CampaignStatsResponse:
        campaign = self._get_owned(user, campaign_id)
        rows = self.db.execute(
            select(CampaignRecipient.status, func.count())
            .where(CampaignRecipient.campaign_id == campaign.id)
            .group_by(CampaignRecipient.status)
        ).all()
        by_status = {status: count for status, count in rows}
        pending = by_status.get(CampaignRecipientStatus.PENDING.value, 0)
        invalid = by_status.get(CampaignRecipientStatus.INVALID.value, 0)
        suppressed = by_status.get(CampaignRecipientStatus.SUPPRESSED.value, 0)
        excluded = by_status.get(CampaignRecipientStatus.EXCLUDED.value, 0)
        total = sum(by_status.values())
        return self._stats_for_campaign(campaign.id)

    def list_recipients(
        self,
        user: User,
        campaign_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        status: str | None = None,
    ) -> PaginatedRecipientsResponse:
        campaign = self._get_owned(user, campaign_id)
        filters = [CampaignRecipient.campaign_id == campaign.id]
        if status:
            filters.append(CampaignRecipient.status == status)
        from sqlalchemy import and_

        where = and_(*filters)
        total = self.db.scalar(
            select(func.count()).select_from(CampaignRecipient).where(where)
        ) or 0
        rows = list(
            self.db.scalars(
                select(CampaignRecipient)
                .options(joinedload(CampaignRecipient.contact))
                .where(where)
                .order_by(CampaignRecipient.id.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).unique().all()
        )
        items = []
        for row in rows:
            contact = row.contact
            items.append(
                CampaignRecipientResponse(
                    id=row.id,
                    campaign_id=row.campaign_id,
                    contact_id=row.contact_id,
                    status=row.status,
                    exclusion_reason=row.exclusion_reason,
                    email=contact.email if contact else None,
                    first_name=contact.first_name if contact else None,
                    last_name=contact.last_name if contact else None,
                    company=contact.company if contact else None,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        return PaginatedRecipientsResponse(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    # ------------------------------------------------------------------
    # Validation / ready / preview
    # ------------------------------------------------------------------

    def validate(self, user: User, campaign_id: UUID) -> CampaignValidationResponse:
        campaign = self._get_owned(user, campaign_id, load_relations=True)
        return self._validate(campaign, user)

    def mark_ready(self, user: User, campaign_id: UUID) -> CampaignResponse:
        campaign = self._get_owned(user, campaign_id, load_relations=True)
        if campaign.status != CampaignStatus.DRAFT.value:
            raise ValidationAppError("Only draft campaigns can be marked ready.")

        validation = self._validate(campaign, user)
        if not validation.valid:
            raise ValidationAppError(
                "Campaign is not ready. " + "; ".join(validation.errors),
                details={"errors": validation.errors, "warnings": validation.warnings},
            )

        subject, html, plain = self._resolve_content(campaign, for_snapshot=True)
        campaign.snapshot_subject = subject
        campaign.snapshot_html = html
        campaign.snapshot_plain_text = plain

        # Freeze effective limits onto campaign
        effective = self._effective_limits(campaign)
        campaign.daily_limit = effective.daily_limit
        campaign.hourly_limit = effective.hourly_limit
        campaign.minimum_delay_seconds = effective.minimum_delay_seconds
        campaign.maximum_delay_seconds = effective.maximum_delay_seconds

        campaign.status = CampaignStatus.READY.value
        campaign.ready_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(campaign)
        campaign = self._get_owned(user, campaign.id, load_relations=True)
        logger.info("campaign.marked_ready", user_id=str(user.id), campaign_id=str(campaign.id))
        return self._to_response(campaign, include_relations=True, include_stats=True)

    def preview(
        self,
        user: User,
        campaign_id: UUID,
        data: CampaignPreviewRequest,
    ) -> CampaignPreviewResponse:
        campaign = self._get_owned(user, campaign_id, load_relations=True)
        subject_src, html_src, plain_src = self._resolve_content(campaign)

        eligible_ids = list(
            self.db.scalars(
                select(CampaignRecipient.contact_id)
                .where(
                    CampaignRecipient.campaign_id == campaign.id,
                    CampaignRecipient.status == CampaignRecipientStatus.PENDING.value,
                )
                .order_by(CampaignRecipient.id.asc())
            ).all()
        )
        if not eligible_ids:
            raise ValidationAppError("No eligible recipients to preview. Snapshot recipients first.")

        contact_id = data.contact_id or eligible_ids[0]
        if contact_id not in eligible_ids:
            # Allow preview of owned pending recipient only
            raise NotFoundError("Eligible recipient not found for this campaign.")

        contact = self.db.scalar(
            select(Contact)
            .join(ContactList, Contact.contact_list_id == ContactList.id)
            .where(Contact.id == contact_id, ContactList.user_id == user.id)
        )
        if not contact:
            raise NotFoundError("Contact not found.")

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
            subject=subject_src,
            html_content=html_src,
            plain_text_content=plain_src,
            context=context,
        )

        idx = eligible_ids.index(contact_id)
        prev_id = eligible_ids[idx - 1] if idx > 0 else None
        next_id = eligible_ids[idx + 1] if idx < len(eligible_ids) - 1 else None

        return CampaignPreviewResponse(
            contact_id=contact.id,
            email=contact.email,
            first_name=contact.first_name,
            last_name=contact.last_name,
            company=contact.company,
            rendered_subject=rendered.rendered_subject,
            rendered_html=rendered.rendered_html,
            rendered_text=rendered.rendered_text,
            warnings=rendered.warnings,
            has_previous=prev_id is not None,
            has_next=next_id is not None,
            previous_contact_id=prev_id,
            next_contact_id=next_id,
            position=idx + 1,
            total_eligible=len(eligible_ids),
        )

    def review(self, user: User, campaign_id: UUID) -> CampaignReviewResponse:
        campaign = self._get_owned(user, campaign_id, load_relations=True)
        return CampaignReviewResponse(
            campaign=self._to_response(campaign, include_relations=True, include_stats=True),
            validation=self._validate(campaign, user),
            message="No emails will be sent yet.",
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _validate(self, campaign: Campaign, user: User) -> CampaignValidationResponse:
        errors: list[str] = []
        warnings: list[str] = []

        if not campaign.name or not campaign.name.strip():
            errors.append("Campaign name is required.")

        if not campaign.email_account_id:
            errors.append("Select a connected email account.")
        else:
            account = campaign.email_account or self.db.get(
                EmailAccount, campaign.email_account_id
            )
            if not account or account.user_id != user.id:
                errors.append("Selected email account is invalid.")
            else:
                if not account.is_active:
                    errors.append("Selected email account is inactive.")
                if account.connection_status != ConnectionStatus.CONNECTED.value:
                    errors.append(
                        "Selected email account is not connected. Reconnect Gmail before marking ready."
                    )

        subject, html, plain = self._resolve_content(campaign)
        if not subject or not subject.strip():
            errors.append("Campaign subject is required.")
        if not html or not html.strip():
            errors.append("Campaign content is required.")
        if not campaign.template_id and not campaign.html_override and not campaign.snapshot_html:
            if not html.strip():
                errors.append("Select a template or provide custom content.")

        stats = self.get_stats(user, campaign.id)
        if stats.total == 0:
            errors.append("Snapshot recipients from a contact list.")
        elif stats.eligible == 0:
            errors.append("Campaign has no eligible recipients.")

        try:
            self._effective_limits(campaign)
        except ValidationAppError as exc:
            errors.append(exc.message)

        if stats.eligible >= 5000:
            warnings.append(
                f"Large audience: {stats.eligible} eligible recipients. Sending will be rate-limited in Phase 7."
            )

        # Personalization quality (only variables actually used)
        used_vars = self._extract_variables(f"{subject}\n{html}\n{plain or ''}")
        if not used_vars:
            warnings.append("No personalization variables found in campaign content.")
        else:
            warnings.extend(
                self._personalization_warnings(campaign, used_vars, stats.eligible)
            )

        if plain is None or not str(plain).strip():
            warnings.append("Plain-text fallback will be auto-generated from HTML.")

        return CampaignValidationResponse(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            eligible_recipients=stats.eligible,
        )

    def _personalization_warnings(
        self,
        campaign: Campaign,
        used_vars: set[str],
        eligible: int,
    ) -> list[str]:
        if eligible == 0:
            return []
        field_map = {
            "first_name": Contact.first_name,
            "last_name": Contact.last_name,
            "company": Contact.company,
            "phone": Contact.phone,
            "website": Contact.website,
        }
        warnings: list[str] = []
        for var, column in field_map.items():
            if var not in used_vars:
                continue
            missing = self.db.scalar(
                select(func.count())
                .select_from(CampaignRecipient)
                .join(Contact, Contact.id == CampaignRecipient.contact_id)
                .where(
                    CampaignRecipient.campaign_id == campaign.id,
                    CampaignRecipient.status == CampaignRecipientStatus.PENDING.value,
                    or_(column.is_(None), column == ""),
                )
            ) or 0
            if missing:
                warnings.append(
                    f"{missing} recipients have no {var.replace('_', ' ')}; fallback will be used."
                )
        return warnings

    def _extract_variables(self, text: str) -> set[str]:
        return {m.group(1) for m in VARIABLE_PATTERN.finditer(text or "")}

    def _resolve_content(
        self,
        campaign: Campaign,
        *,
        for_snapshot: bool = False,
    ) -> tuple[str, str, str | None]:
        if campaign.status == CampaignStatus.READY.value and campaign.snapshot_subject:
            return (
                campaign.snapshot_subject,
                campaign.snapshot_html or "",
                campaign.snapshot_plain_text,
            )
        if for_snapshot or campaign.snapshot_subject:
            # Prefer overrides, then template
            pass

        if campaign.subject_override or campaign.html_override:
            subject = campaign.subject_override
            html = campaign.html_override
            plain = campaign.plain_text_override
            if campaign.template_id and (not subject or not html):
                template = campaign.template or self.db.get(EmailTemplate, campaign.template_id)
                if template:
                    subject = subject or template.subject
                    html = html or template.html_content
                    if plain is None:
                        plain = template.plain_text_content
            subject = subject or ""
            html = sanitize_email_html(html or "")
            if plain is None:
                plain = html_to_plain_text(html)
            return subject, html, plain

        if campaign.template_id:
            template = campaign.template or self.db.get(EmailTemplate, campaign.template_id)
            if template:
                html = sanitize_email_html(template.html_content)
                plain = template.plain_text_content or html_to_plain_text(html)
                return template.subject, html, plain

        return "", "", None

    def _effective_limits(self, campaign: Campaign) -> EffectiveLimits:
        account = campaign.email_account
        if campaign.email_account_id and not account:
            account = self.db.get(EmailAccount, campaign.email_account_id)

        defaults_daily = account.daily_send_limit if account else 100
        defaults_hourly = account.hourly_send_limit if account else 20
        defaults_min = account.minimum_delay_seconds if account else 30
        defaults_max = account.maximum_delay_seconds if account else 90

        daily = campaign.daily_limit if campaign.daily_limit is not None else defaults_daily
        hourly = campaign.hourly_limit if campaign.hourly_limit is not None else defaults_hourly
        min_d = (
            campaign.minimum_delay_seconds
            if campaign.minimum_delay_seconds is not None
            else defaults_min
        )
        max_d = (
            campaign.maximum_delay_seconds
            if campaign.maximum_delay_seconds is not None
            else defaults_max
        )

        if daily < 1 or hourly < 1:
            raise ValidationAppError("Sending limits must be at least 1.")
        if hourly > daily:
            raise ValidationAppError("Hourly limit cannot exceed daily limit.")
        if max_d < min_d:
            raise ValidationAppError("Maximum delay must be >= minimum delay.")

        if account:
            if daily > account.daily_send_limit:
                raise ValidationAppError(
                    f"Campaign daily limit cannot exceed account limit ({account.daily_send_limit})."
                )
            if hourly > account.hourly_send_limit:
                raise ValidationAppError(
                    f"Campaign hourly limit cannot exceed account limit ({account.hourly_send_limit})."
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
            minimum_delay_seconds=min_d,
            maximum_delay_seconds=max_d,
            inherited_from_account=inherited,
        )

    def _apply_limit_updates(
        self,
        campaign: Campaign,
        data: CampaignUpdate,
        user: User,
    ) -> None:
        if data.daily_limit is not None:
            campaign.daily_limit = data.daily_limit
        if data.hourly_limit is not None:
            campaign.hourly_limit = data.hourly_limit
        if data.minimum_delay_seconds is not None:
            campaign.minimum_delay_seconds = data.minimum_delay_seconds
        if data.maximum_delay_seconds is not None:
            campaign.maximum_delay_seconds = data.maximum_delay_seconds

        # Validate against account if present
        if any(
            v is not None
            for v in (
                data.daily_limit,
                data.hourly_limit,
                data.minimum_delay_seconds,
                data.maximum_delay_seconds,
            )
        ):
            self._effective_limits(campaign)

    def _classify_contact(
        self,
        contact: Contact,
        skip_suppressed: bool,
    ) -> tuple[str, str | None]:
        status = contact.status
        if isinstance(status, ContactStatus):
            key = status
        else:
            try:
                key = ContactStatus(str(status))
            except ValueError:
                return CampaignRecipientStatus.EXCLUDED.value, "Unknown contact status"

        if key == ContactStatus.ACTIVE:
            return CampaignRecipientStatus.PENDING.value, None

        if key in EXCLUDED_STATUSES:
            recip_status, reason = EXCLUDED_STATUSES[key]
            if not skip_suppressed and key in {
                ContactStatus.UNSUBSCRIBED,
                ContactStatus.SUPPRESSED,
                ContactStatus.BOUNCED,
            }:
                # Still exclude for Phase 6 safety even if flag off — document
                return recip_status, reason
            return recip_status, reason

        return CampaignRecipientStatus.EXCLUDED.value, "Not eligible"

    def _get_owned(
        self,
        user: User,
        campaign_id: UUID,
        *,
        load_relations: bool = False,
    ) -> Campaign:
        stmt = select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.user_id == user.id,
        )
        if load_relations:
            stmt = stmt.options(
                joinedload(Campaign.email_account),
                joinedload(Campaign.template),
                joinedload(Campaign.contact_list),
            )
        campaign = self.db.scalars(stmt).unique().first()
        if not campaign:
            raise NotFoundError("Campaign not found.")
        return campaign

    def _get_owned_account(self, user: User, account_id: UUID) -> EmailAccount:
        account = self.db.scalar(
            select(EmailAccount).where(
                EmailAccount.id == account_id,
                EmailAccount.user_id == user.id,
            )
        )
        if not account:
            raise NotFoundError("Email account not found.")
        return account

    def _get_owned_template(self, user: User, template_id: UUID) -> EmailTemplate:
        template = self.db.scalar(
            select(EmailTemplate).where(
                EmailTemplate.id == template_id,
                EmailTemplate.user_id == user.id,
            )
        )
        if not template:
            raise NotFoundError("Template not found.")
        return template

    def _get_owned_list(self, user: User, list_id: UUID) -> ContactList:
        contact_list = self.db.scalar(
            select(ContactList).where(
                ContactList.id == list_id,
                ContactList.user_id == user.id,
            )
        )
        if not contact_list:
            raise NotFoundError("Contact list not found.")
        return contact_list

    def _to_response(
        self,
        campaign: Campaign,
        *,
        include_relations: bool = False,
        include_stats: bool = False,
    ) -> CampaignResponse:
        account_summary = None
        template_summary = None
        list_summary = None
        effective = None
        content_source = None

        if include_relations:
            if campaign.email_account:
                a = campaign.email_account
                account_summary = AccountSummary(
                    id=a.id,
                    email_address=a.email_address,
                    provider=a.provider,
                    connection_status=a.connection_status,
                    daily_send_limit=a.daily_send_limit,
                    hourly_send_limit=a.hourly_send_limit,
                    minimum_delay_seconds=a.minimum_delay_seconds,
                    maximum_delay_seconds=a.maximum_delay_seconds,
                    is_active=a.is_active,
                )
            if campaign.template:
                t = campaign.template
                template_summary = TemplateSummary(
                    id=t.id,
                    name=t.name,
                    subject=t.subject,
                )
            if campaign.contact_list:
                cl = campaign.contact_list
                list_summary = ContactListSummary(
                    id=cl.id,
                    name=cl.name,
                    total_contacts=cl.total_contacts,
                )
            try:
                effective = self._effective_limits(campaign)
            except ValidationAppError:
                effective = None

            if campaign.snapshot_subject:
                content_source = "snapshot"
            elif campaign.html_override or campaign.subject_override:
                content_source = "custom"
            elif campaign.template_id:
                content_source = "template"

        stats = self._stats_for_campaign(campaign.id) if include_stats else None

        return CampaignResponse(
            id=campaign.id,
            name=campaign.name,
            description=campaign.description,
            status=campaign.status,
            email_account_id=campaign.email_account_id,
            template_id=campaign.template_id,
            contact_list_id=campaign.contact_list_id,
            subject_override=campaign.subject_override,
            html_override=campaign.html_override,
            plain_text_override=campaign.plain_text_override,
            has_content_snapshot=bool(campaign.snapshot_subject),
            snapshot_subject=campaign.snapshot_subject,
            daily_limit=campaign.daily_limit,
            hourly_limit=campaign.hourly_limit,
            minimum_delay_seconds=campaign.minimum_delay_seconds,
            maximum_delay_seconds=campaign.maximum_delay_seconds,
            stop_on_reply=campaign.stop_on_reply,
            skip_suppressed=campaign.skip_suppressed,
            ready_at=campaign.ready_at,
            started_at=campaign.started_at,
            paused_at=campaign.paused_at,
            completed_at=campaign.completed_at,
            cancelled_at=campaign.cancelled_at,
            last_activity_at=campaign.last_activity_at,
            created_at=campaign.created_at,
            updated_at=campaign.updated_at,
            email_account=account_summary,
            template=template_summary,
            contact_list=list_summary,
            stats=stats,
            effective_limits=effective,
            content_source=content_source,
        )

    def _stats_for_campaign(self, campaign_id: UUID) -> CampaignStatsResponse:
        from app.services.campaign_delivery_service import CampaignDeliveryService

        campaign = self.db.get(Campaign, campaign_id)
        rows = self.db.execute(
            select(CampaignRecipient.status, func.count())
            .where(CampaignRecipient.campaign_id == campaign_id)
            .group_by(CampaignRecipient.status)
        ).all()
        by_status = {status: count for status, count in rows}
        total = sum(by_status.values())
        pending = by_status.get(CampaignRecipientStatus.PENDING.value, 0)
        delivery = (
            CampaignDeliveryService(self.db).build_delivery_stats(campaign)
            if campaign
            else {}
        )
        eligible_delivery = delivery.get("messages_total", 0) or (
            by_status.get(CampaignRecipientStatus.QUEUED.value, 0)
            + by_status.get(CampaignRecipientStatus.SENT.value, 0)
            + by_status.get(CampaignRecipientStatus.FAILED.value, 0)
            + by_status.get(CampaignRecipientStatus.SENDING.value, 0)
        )
        return CampaignStatsResponse(
            total=total,
            total_recipients=total,
            eligible=eligible_delivery or pending,
            pending=pending,
            excluded=by_status.get(CampaignRecipientStatus.EXCLUDED.value, 0),
            invalid=by_status.get(CampaignRecipientStatus.INVALID.value, 0),
            suppressed=by_status.get(CampaignRecipientStatus.SUPPRESSED.value, 0),
            queued=by_status.get(CampaignRecipientStatus.QUEUED.value, 0),
            sending=by_status.get(CampaignRecipientStatus.SENDING.value, 0),
            sent=by_status.get(CampaignRecipientStatus.SENT.value, 0),
            failed=by_status.get(CampaignRecipientStatus.FAILED.value, 0),
            cancelled=by_status.get(CampaignRecipientStatus.CANCELLED.value, 0),
            replied=by_status.get(CampaignRecipientStatus.REPLIED.value, 0),
            messages_total=delivery.get("messages_total", 0),
            messages_queued=delivery.get("messages_queued", 0),
            messages_sending=delivery.get("messages_sending", 0),
            messages_sent=delivery.get("messages_sent", 0),
            messages_failed=delivery.get("messages_failed", 0),
            messages_cancelled=delivery.get("messages_cancelled", 0),
            progress_percent=delivery.get("progress_percent", 0.0),
            started_at=delivery.get("started_at"),
            completed_at=delivery.get("completed_at"),
            last_activity_at=delivery.get("last_activity_at"),
        )
