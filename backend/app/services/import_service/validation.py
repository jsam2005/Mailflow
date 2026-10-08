"""Import row mapping and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.contact import Contact
from app.services.import_service.column_mapping import (
    json_safe,
    split_full_name,
    validate_mapping,
)
from app.utils.email import normalize_email


@dataclass
class MappedContactRow:
    row_number: int
    email: str | None = None
    normalized_email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    phone: str | None = None
    website: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    issue: str | None = None  # missing_email | invalid_email | duplicate_in_file | duplicate_existing
    raw: dict[str, str | None] = field(default_factory=dict)


@dataclass
class ValidationResult:
    total_rows: int
    valid_rows: int
    invalid_email_rows: int
    missing_email_rows: int
    duplicate_in_file_rows: int
    duplicate_existing_rows: int
    importable_rows: int
    skipped_rows: int
    importable: list[MappedContactRow]
    invalid_emails: list[MappedContactRow]
    missing_emails: list[MappedContactRow]
    duplicates_in_file: list[MappedContactRow]
    duplicates_existing: list[MappedContactRow]

    def summary_dict(self) -> dict[str, Any]:
        return {
            "total_rows": self.total_rows,
            "valid_rows": self.valid_rows,
            "invalid_email_rows": self.invalid_email_rows,
            "missing_email_rows": self.missing_email_rows,
            "duplicate_in_file_rows": self.duplicate_in_file_rows,
            "duplicate_existing_rows": self.duplicate_existing_rows,
            "importable_rows": self.importable_rows,
            "skipped_rows": self.skipped_rows,
            "sample_invalid_emails": [_row_preview(r) for r in self.invalid_emails[:100]],
            "sample_missing_emails": [_row_preview(r) for r in self.missing_emails[:100]],
            "sample_duplicates_in_file": [_row_preview(r) for r in self.duplicates_in_file[:100]],
            "sample_duplicates_existing": [
                _row_preview(r) for r in self.duplicates_existing[:100]
            ],
        }


def _row_preview(row: MappedContactRow) -> dict[str, Any]:
    return {
        "row_number": row.row_number,
        "email": row.email,
        "reason": _reason_label(row.issue),
        "first_name": row.first_name,
        "last_name": row.last_name,
        "company": row.company,
    }


def _reason_label(issue: str | None) -> str:
    return {
        "missing_email": "Missing email",
        "invalid_email": "Invalid email address",
        "duplicate_in_file": "Duplicate email in file",
        "duplicate_existing": "Email already exists in contact list",
    }.get(issue or "", issue or "Unknown")


def map_raw_row(
    row_number: int,
    raw: dict[str, str | None],
    mapping: dict[str, str],
) -> MappedContactRow:
    validate_mapping(mapping)
    mapped = MappedContactRow(row_number=row_number, raw=raw)
    full_name: str | None = None

    for source, target in mapping.items():
        value = raw.get(source)
        if target in {"ignore", ""} or target is None:
            continue
        if target == "custom":
            if value is not None:
                mapped.metadata[source] = json_safe(value)
            continue
        if target == "email":
            mapped.email = value
        elif target == "first_name":
            mapped.first_name = value
        elif target == "last_name":
            mapped.last_name = value
        elif target == "full_name":
            full_name = value
        elif target == "company":
            mapped.company = value
        elif target == "phone":
            mapped.phone = value
        elif target == "website":
            mapped.website = value

    if full_name:
        mapped.metadata.setdefault("full_name", full_name)
        if not mapped.first_name and not mapped.last_name:
            first, last = split_full_name(full_name)
            mapped.first_name = first
            mapped.last_name = last

    return mapped


def classify_email(row: MappedContactRow) -> MappedContactRow:
    if not row.email or not str(row.email).strip():
        row.issue = "missing_email"
        return row

    cleaned = str(row.email).strip()
    try:
        result = validate_email(cleaned, check_deliverability=False)
    except EmailNotValidError:
        row.issue = "invalid_email"
        return row

    row.email = result.normalized
    row.normalized_email = normalize_email(result.normalized)
    return row


class ImportValidationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def validate_rows(
        self,
        rows: list[tuple[int, dict[str, str | None]]],
        mapping: dict[str, str],
        contact_list_id: UUID | None,
    ) -> ValidationResult:
        validate_mapping(mapping)

        mapped_rows = [classify_email(map_raw_row(num, raw, mapping)) for num, raw in rows]

        missing = [r for r in mapped_rows if r.issue == "missing_email"]
        invalid = [r for r in mapped_rows if r.issue == "invalid_email"]
        candidates = [r for r in mapped_rows if r.issue is None and r.normalized_email]

        seen: set[str] = set()
        importable: list[MappedContactRow] = []
        dup_file: list[MappedContactRow] = []
        for row in candidates:
            assert row.normalized_email is not None
            if row.normalized_email in seen:
                row.issue = "duplicate_in_file"
                dup_file.append(row)
            else:
                seen.add(row.normalized_email)
                importable.append(row)

        dup_existing: list[MappedContactRow] = []
        if contact_list_id and importable:
            existing = self._existing_emails(
                contact_list_id,
                [r.normalized_email for r in importable if r.normalized_email],
            )
            remaining: list[MappedContactRow] = []
            for row in importable:
                if row.normalized_email in existing:
                    row.issue = "duplicate_existing"
                    dup_existing.append(row)
                else:
                    remaining.append(row)
            importable = remaining

        total = len(mapped_rows)
        skipped = len(missing) + len(invalid) + len(dup_file) + len(dup_existing)
        return ValidationResult(
            total_rows=total,
            valid_rows=len(importable),
            invalid_email_rows=len(invalid),
            missing_email_rows=len(missing),
            duplicate_in_file_rows=len(dup_file),
            duplicate_existing_rows=len(dup_existing),
            importable_rows=len(importable),
            skipped_rows=skipped,
            importable=importable,
            invalid_emails=invalid,
            missing_emails=missing,
            duplicates_in_file=dup_file,
            duplicates_existing=dup_existing,
        )

    def _existing_emails(self, list_id: UUID, emails: list[str]) -> set[str]:
        if not emails:
            return set()
        existing: set[str] = set()
        chunk_size = 500
        for i in range(0, len(emails), chunk_size):
            chunk = emails[i : i + chunk_size]
            stmt = select(Contact.normalized_email).where(
                Contact.contact_list_id == list_id,
                Contact.normalized_email.in_(chunk),
            )
            existing.update(self.db.scalars(stmt).all())
        return existing
