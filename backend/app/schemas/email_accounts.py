"""Email account API schemas (tokens never included)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class GoogleConnectResponse(BaseModel):
    authorization_url: str


class EmailAccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider: str
    email_address: str
    display_name: str | None
    daily_send_limit: int
    hourly_send_limit: int
    minimum_delay_seconds: int
    maximum_delay_seconds: int
    sent_today: int
    connection_status: str
    last_connection_check_at: datetime | None
    last_connection_error: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class EmailAccountListResponse(BaseModel):
    items: list[EmailAccountResponse]


class EmailAccountUpdate(BaseModel):
    daily_send_limit: int | None = Field(default=None, ge=1, le=2000)
    hourly_send_limit: int | None = Field(default=None, ge=1, le=500)
    minimum_delay_seconds: int | None = Field(default=None, ge=1, le=3600)
    maximum_delay_seconds: int | None = Field(default=None, ge=1, le=7200)

    @model_validator(mode="after")
    def validate_limits(self) -> "EmailAccountUpdate":
        # Cross-field checks applied after merge in service when partial.
        if (
            self.daily_send_limit is not None
            and self.hourly_send_limit is not None
            and self.hourly_send_limit > self.daily_send_limit
        ):
            raise ValueError("Hourly send limit cannot exceed daily send limit.")
        if (
            self.minimum_delay_seconds is not None
            and self.maximum_delay_seconds is not None
            and self.maximum_delay_seconds < self.minimum_delay_seconds
        ):
            raise ValueError("Maximum delay must be greater than or equal to minimum delay.")
        return self


class ConnectionTestResponse(BaseModel):
    connected: bool
    email_address: str | None = None
    message: str


class SendTestEmailRequest(BaseModel):
    to_email: EmailStr
    mode: str = Field(default="simple")  # simple | template
    subject: str | None = Field(default=None, max_length=255)
    message: str | None = Field(default=None, max_length=50_000)
    template_id: UUID | None = None
    contact_id: UUID | None = None

    @field_validator("mode")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        normalized = (value or "simple").strip().lower()
        if normalized not in {"simple", "template"}:
            raise ValueError("mode must be 'simple' or 'template'")
        return normalized


class SendTestEmailResponse(BaseModel):
    sent: bool
    to_email: str
    subject: str
    provider_message_id: str | None = None
    thread_id: str | None = None
    timestamp: datetime
    message: str
