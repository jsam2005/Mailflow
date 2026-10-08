"""Campaign email message API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EmailMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID
    campaign_recipient_id: UUID
    contact_id: UUID
    email_account_id: UUID
    to_email: str
    to_name: str | None
    subject: str
    rendered_html: str
    rendered_text: str | None
    status: str
    provider_message_id: str | None
    provider_thread_id: str | None
    rfc_message_id: str | None
    attempt_count: int
    max_attempts: int
    last_attempt_at: datetime | None
    next_attempt_at: datetime | None
    sent_at: datetime | None
    failed_at: datetime | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class PaginatedEmailMessagesResponse(BaseModel):
    items: list[EmailMessageResponse]
    page: int
    page_size: int
    total: int
    total_pages: int
