"""Column alias detection for contact imports."""

from __future__ import annotations

import re
from typing import Any


TARGET_FIELDS = (
    "email",
    "first_name",
    "last_name",
    "full_name",
    "company",
    "phone",
    "website",
    "custom",
    "ignore",
)

ALIASES: dict[str, list[str]] = {
    "email": [
        "email",
        "email address",
        "email_id",
        "emailid",
        "mail",
        "mail id",
        "mail_id",
        "e-mail",
        "business email",
        "work email",
    ],
    "first_name": [
        "first name",
        "firstname",
        "first_name",
        "given name",
    ],
    "last_name": [
        "last name",
        "lastname",
        "last_name",
        "surname",
    ],
    "full_name": [
        "name",
        "full name",
        "fullname",
        "contact name",
        "customer name",
        "contact person",
    ],
    "company": [
        "company",
        "company name",
        "business",
        "business name",
        "organization",
        "organisation",
    ],
    "phone": [
        "phone",
        "phone number",
        "mobile",
        "mobile number",
        "contact number",
        "telephone",
    ],
    "website": [
        "website",
        "url",
        "company website",
        "site",
        "web",
    ],
}


def normalize_header(header: str) -> str:
    value = header.strip().lower()
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value)
    return value


def suggest_column_mapping(columns: list[str]) -> dict[str, str]:
    """Return mapping of source column -> target field for confident aliases only."""
    used_targets: set[str] = set()
    mapping: dict[str, str] = {}

    alias_lookup: dict[str, str] = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            alias_lookup[normalize_header(alias)] = target

    for column in columns:
        key = normalize_header(column)
        target = alias_lookup.get(key)
        if target and target not in used_targets:
            mapping[column] = target
            used_targets.add(target)

    return mapping


def validate_mapping(mapping: dict[str, str]) -> None:
    from app.core.exceptions import ValidationAppError

    if not mapping:
        raise ValidationAppError("Column mapping is required")

    targets = [target for target in mapping.values() if target not in {"ignore", "custom", ""}]
    if "email" not in targets:
        raise ValidationAppError("Map one column to Email before continuing.")

    seen: set[str] = set()
    for target in targets:
        if target in seen:
            raise ValidationAppError(
                f"Only one column can map to {target.replace('_', ' ').title()}",
                details={"target": target},
            )
        seen.add(target)


def split_full_name(full_name: str) -> tuple[str | None, str | None]:
    parts = [part for part in full_name.strip().split() if part]
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], " ".join(parts[1:])


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        if value.is_integer():
            return int(value)
        return value
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)
