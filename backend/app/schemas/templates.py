"""Email template and asset schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmailTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    subject: str = Field(min_length=1, max_length=255)
    html_content: str = Field(min_length=1)
    plain_text_content: str | None = None
    plain_text_customized: bool = False
    is_active: bool = True


class EmailTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    subject: str | None = Field(default=None, min_length=1, max_length=255)
    html_content: str | None = Field(default=None, min_length=1)
    plain_text_content: str | None = None
    plain_text_customized: bool | None = None
    is_active: bool | None = None


class EmailTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    subject: str
    html_content: str
    plain_text_content: str | None
    plain_text_customized: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    warnings: list[str] = Field(default_factory=list)


class PaginatedTemplatesResponse(BaseModel):
    items: list[EmailTemplateResponse]
    page: int
    page_size: int
    total: int
    total_pages: int


class TemplateRenderRequest(BaseModel):
    contact_id: UUID | None = None
    sample_data: dict[str, Any] | None = None


class TemplatePreviewRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=255)
    html_content: str = Field(min_length=1)
    plain_text_content: str | None = None
    contact_id: UUID | None = None
    sample_data: dict[str, Any] | None = None


class TemplateRenderResponse(BaseModel):
    rendered_subject: str
    rendered_html: str
    rendered_text: str
    warnings: list[str]
    used_variables: list[str]
    missing_variables: list[str]
    preview_mode: str = "contact"  # contact | sample


class TemplateAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    template_id: UUID | None
    original_filename: str
    mime_type: str
    file_size: int
    width: int | None
    height: int | None
    content_id: str | None
    preview_url: str
    cid_placeholder: str | None
    created_at: datetime
