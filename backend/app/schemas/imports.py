"""Import API schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ImportUploadResponse(BaseModel):
    import_session_id: UUID
    original_filename: str
    file_type: str
    total_rows: int
    columns: list[str]
    preview_rows: list[dict[str, Any]]
    suggested_mapping: dict[str, str]
    sheets: list[str] = Field(default_factory=list)
    default_sheet: str | None = None
    status: str


class ImportValidateRequest(BaseModel):
    column_mapping: dict[str, str]
    sheet: str | None = None
    contact_list_id: UUID | None = None


class ImportIssueRow(BaseModel):
    row_number: int
    email: str | None = None
    reason: str
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None


class ImportValidationResponse(BaseModel):
    total_rows: int
    valid_rows: int
    invalid_email_rows: int
    missing_email_rows: int
    duplicate_in_file_rows: int
    duplicate_existing_rows: int
    importable_rows: int
    skipped_rows: int
    sample_invalid_emails: list[ImportIssueRow] = Field(default_factory=list)
    sample_missing_emails: list[ImportIssueRow] = Field(default_factory=list)
    sample_duplicates_in_file: list[ImportIssueRow] = Field(default_factory=list)
    sample_duplicates_existing: list[ImportIssueRow] = Field(default_factory=list)


class ImportExecuteRequest(BaseModel):
    contact_list_id: UUID | None = None
    column_mapping: dict[str, str] | None = None
    sheet: str | None = None
    new_list_name: str | None = Field(default=None, max_length=255)
    new_list_description: str | None = Field(default=None, max_length=5000)


class ImportExecuteResponse(BaseModel):
    import_session_id: UUID
    contact_list_id: UUID
    contact_list_name: str
    status: str
    imported_rows: int
    skipped_rows: int
    total_rows: int
    invalid_email_rows: int
    missing_email_rows: int
    duplicate_in_file_rows: int
    duplicate_existing_rows: int


class ImportSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contact_list_id: UUID | None
    contact_list_name: str | None = None
    original_filename: str
    file_type: str
    status: str
    selected_sheet: str | None = None
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    missing_email_rows: int
    imported_rows: int
    skipped_rows: int
    column_mapping: dict[str, Any] | None = None
    validation_summary: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
