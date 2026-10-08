"""Email validation and normalization helpers."""

from email_validator import EmailNotValidError, validate_email

from app.core.exceptions import ValidationAppError


def normalize_email(email: str) -> str:
    """Return a trimmed, lowercased email address without validating deliverability."""
    return email.strip().lower()


def validate_and_normalize_email(email: str) -> tuple[str, str]:
    """
    Validate an email and return (display_email, normalized_email).

    display_email preserves the original local-part casing from the validated form
    when available; normalized_email is always lowercase.
    """
    cleaned = email.strip()
    if not cleaned:
        raise ValidationAppError(
            "Invalid email address",
            details={"field": "email"},
        )

    try:
        result = validate_email(cleaned, check_deliverability=False)
    except EmailNotValidError as exc:
        raise ValidationAppError(
            "Invalid email address",
            details={"field": "email", "reason": str(exc)},
        ) from exc

    # normalized includes lowercased domain; use lowercase for uniqueness key
    normalized = normalize_email(result.normalized)
    display = result.normalized
    return display, normalized
