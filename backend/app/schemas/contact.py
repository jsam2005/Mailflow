"""Contact schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.contact import ContactStatus


class ContactCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    website: str | None = Field(default=None, max_length=512)
    contact_metadata: dict[str, Any] | None = Field(default=None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class ContactUpdate(BaseModel):
    email: str | None = Field(default=None, min_length=3, max_length=320)
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    website: str | None = Field(default=None, max_length=512)
    status: ContactStatus | None = None
    contact_metadata: dict[str, Any] | None = Field(default=None, alias="metadata")

    model_config = ConfigDict(populate_by_name=True)


class ContactResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        ser_json_by_alias=True,
    )

    id: UUID
    contact_list_id: UUID
    contact_list_name: str | None = None
    email: str
    first_name: str | None
    last_name: str | None
    company: str | None
    phone: str | None
    website: str | None
    status: ContactStatus
    contact_metadata: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias="contact_metadata",
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime


class PaginatedContactResponse(BaseModel):
    items: list[ContactResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class ContactBulkDeleteRequest(BaseModel):
    contact_ids: list[UUID] = Field(min_length=1, max_length=500)


class ContactBulkDeleteResponse(BaseModel):
    deleted: int


class ContactStatsResponse(BaseModel):
    total: int
    active: int
    invalid: int
    unsubscribed: int
    bounced: int
    suppressed: int
    contact_lists: int


class ContactListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)
    search: str | None = None
    status: ContactStatus | None = None
    company: str | None = None
    contact_list_id: UUID | None = None
    sort_by: str = "created_at"
    sort_order: str = "desc"

    @field_validator("sort_order")
    @classmethod
    def validate_sort_order(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"asc", "desc"}:
            raise ValueError("sort_order must be 'asc' or 'desc'")
        return normalized

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, value: str) -> str:
        allowed = {"created_at", "email", "first_name", "last_name", "company", "status"}
        if value not in allowed:
            raise ValueError(f"sort_by must be one of: {', '.join(sorted(allowed))}")
        return value
