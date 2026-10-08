"""Campaign planning API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    email_account_id: UUID | None = None
    template_id: UUID | None = None
    contact_list_id: UUID | None = None
    subject_override: str | None = Field(default=None, max_length=255)
    html_override: str | None = None
    plain_text_override: str | None = None
    clear_overrides: bool = False
    daily_limit: int | None = Field(default=None, ge=1, le=2000)
    hourly_limit: int | None = Field(default=None, ge=1, le=500)
    minimum_delay_seconds: int | None = Field(default=None, ge=1, le=3600)
    maximum_delay_seconds: int | None = Field(default=None, ge=1, le=7200)
    stop_on_reply: bool | None = None
    skip_suppressed: bool | None = None
    use_custom_content: bool | None = None

    @model_validator(mode="after")
    def validate_limits(self) -> "CampaignUpdate":
        if (
            self.daily_limit is not None
            and self.hourly_limit is not None
            and self.hourly_limit > self.daily_limit
        ):
            raise ValueError("Hourly limit cannot exceed daily limit.")
        if (
            self.minimum_delay_seconds is not None
            and self.maximum_delay_seconds is not None
            and self.maximum_delay_seconds < self.minimum_delay_seconds
        ):
            raise ValueError("Maximum delay must be >= minimum delay.")
        return self


class AccountSummary(BaseModel):
    id: UUID
    email_address: str
    provider: str
    connection_status: str
    daily_send_limit: int
    hourly_send_limit: int
    minimum_delay_seconds: int
    maximum_delay_seconds: int
    is_active: bool


class TemplateSummary(BaseModel):
    id: UUID
    name: str
    subject: str


class ContactListSummary(BaseModel):
    id: UUID
    name: str
    total_contacts: int


class EffectiveLimits(BaseModel):
    daily_limit: int
    hourly_limit: int
    minimum_delay_seconds: int
    maximum_delay_seconds: int
    inherited_from_account: bool


class CampaignStatsResponse(BaseModel):
    total: int = 0
    total_recipients: int = 0
    eligible: int = 0
    pending: int = 0
    excluded: int = 0
    invalid: int = 0
    suppressed: int = 0
    queued: int = 0
    sending: int = 0
    sent: int = 0
    failed: int = 0
    cancelled: int = 0
    replied: int = 0
    messages_total: int = 0
    messages_queued: int = 0
    messages_sending: int = 0
    messages_sent: int = 0
    messages_failed: int = 0
    messages_cancelled: int = 0
    progress_percent: float = 0.0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_activity_at: datetime | None = None


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    status: str
    email_account_id: UUID | None
    template_id: UUID | None
    contact_list_id: UUID | None
    subject_override: str | None
    html_override: str | None
    plain_text_override: str | None
    has_content_snapshot: bool
    snapshot_subject: str | None = None
    daily_limit: int | None
    hourly_limit: int | None
    minimum_delay_seconds: int | None
    maximum_delay_seconds: int | None
    stop_on_reply: bool
    skip_suppressed: bool
    ready_at: datetime | None
    started_at: datetime | None = None
    paused_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None
    last_activity_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    email_account: AccountSummary | None = None
    template: TemplateSummary | None = None
    contact_list: ContactListSummary | None = None
    stats: CampaignStatsResponse | None = None
    effective_limits: EffectiveLimits | None = None
    content_source: str | None = None  # template | custom | snapshot


class CampaignListResponse(BaseModel):
    items: list[CampaignResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class CampaignRecipientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    contact_id: UUID
    status: str
    exclusion_reason: str | None
    email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    created_at: datetime
    updated_at: datetime


class PaginatedRecipientsResponse(BaseModel):
    items: list[CampaignRecipientResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class RecipientSnapshotRequest(BaseModel):
    contact_list_id: UUID


class RecipientSnapshotResponse(BaseModel):
    contact_list_id: UUID
    total: int
    eligible: int
    invalid: int
    suppressed: int
    excluded: int
    stats: CampaignStatsResponse


class CampaignValidationResponse(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]
    eligible_recipients: int


class CampaignPreviewRequest(BaseModel):
    contact_id: UUID | None = None


class CampaignPreviewResponse(BaseModel):
    contact_id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    company: str | None
    rendered_subject: str
    rendered_html: str
    rendered_text: str
    warnings: list[str]
    has_previous: bool
    has_next: bool
    previous_contact_id: UUID | None = None
    next_contact_id: UUID | None = None
    position: int
    total_eligible: int


class CampaignReviewResponse(BaseModel):
    campaign: CampaignResponse
    validation: CampaignValidationResponse
    message: str = "No emails will be sent yet."
