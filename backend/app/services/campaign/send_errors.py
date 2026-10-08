"""Safe send error classification for campaign delivery."""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.exceptions import NotFoundError, OAuthError, ValidationAppError


@dataclass(frozen=True)
class SendErrorInfo:
    code: str
    message: str
    retryable: bool


RETRYABLE_CODES = {
    "RATE_LIMITED",
    "TEMPORARY_PROVIDER_ERROR",
    "QUOTA_EXCEEDED",
}

NON_RETRYABLE_CODES = {
    "AUTH_EXPIRED",
    "INVALID_RECIPIENT",
    "MESSAGE_BUILD_FAILED",
    "ASSET_MISSING",
    "PROVIDER_REJECTED",
    "RECIPIENT_NO_LONGER_ELIGIBLE",
    "TEST_RECIPIENT_NOT_ALLOWED",
    "UNCERTAIN_PROVIDER_RESULT",
    "UNKNOWN",
}


def classify_exception(exc: Exception) -> SendErrorInfo:
    if isinstance(exc, OAuthError):
        return SendErrorInfo(
            code="AUTH_EXPIRED",
            message=exc.message,
            retryable=False,
        )
    if isinstance(exc, NotFoundError):
        msg = str(getattr(exc, "message", exc) or exc)
        if "asset" in msg.lower() or "image" in msg.lower():
            return SendErrorInfo("ASSET_MISSING", msg, retryable=False)
        return SendErrorInfo("MESSAGE_BUILD_FAILED", msg, retryable=False)
    if isinstance(exc, ValidationAppError):
        msg = exc.message.lower()
        if "asset" in msg or "image" in msg:
            return SendErrorInfo("ASSET_MISSING", exc.message, retryable=False)
        # Avoid classifying generic "…email…" provider failures as invalid recipient.
        if "recipient" in msg or "invalid address" in msg:
            return SendErrorInfo("INVALID_RECIPIENT", exc.message, retryable=False)
        if "gmail could not send" in msg or "could not send" in msg:
            return SendErrorInfo(
                "TEMPORARY_PROVIDER_ERROR",
                "Provider temporarily unavailable. Will retry later.",
                retryable=True,
            )
        return SendErrorInfo("MESSAGE_BUILD_FAILED", exc.message, retryable=False)

    # httpx says "timed out" (with a space) — not the substring "timeout".
    if isinstance(exc, httpx.TimeoutException) or isinstance(exc, TimeoutError):
        return SendErrorInfo(
            "TEMPORARY_PROVIDER_ERROR",
            "Provider temporarily unavailable. Will retry later.",
            retryable=True,
        )
    if isinstance(exc, (httpx.NetworkError, httpx.RemoteProtocolError)):
        return SendErrorInfo(
            "TEMPORARY_PROVIDER_ERROR",
            "Provider temporarily unavailable. Will retry later.",
            retryable=True,
        )

    text = str(exc).lower()
    if "429" in text or "rate" in text:
        return SendErrorInfo(
            "RATE_LIMITED",
            "Provider rate limit reached. Will retry later.",
            retryable=True,
        )
    if (
        "timeout" in text
        or "timed out" in text
        or "503" in text
        or "502" in text
        or "500" in text
    ):
        return SendErrorInfo(
            "TEMPORARY_PROVIDER_ERROR",
            "Provider temporarily unavailable. Will retry later.",
            retryable=True,
        )
    if "403" in text or "quota" in text:
        return SendErrorInfo(
            "QUOTA_EXCEEDED",
            "Sending quota reached. Will retry later.",
            retryable=True,
        )
    if "401" in text:
        return SendErrorInfo(
            "AUTH_EXPIRED",
            "Email account requires reconnection.",
            retryable=False,
        )
    return SendErrorInfo(
        "UNKNOWN",
        "Send failed. Please try again later.",
        retryable=False,
    )


def classify_http_status(status_code: int) -> SendErrorInfo:
    if status_code == 429:
        return SendErrorInfo(
            "RATE_LIMITED",
            "Provider rate limit reached. Will retry later.",
            retryable=True,
        )
    if status_code in {500, 502, 503, 504}:
        return SendErrorInfo(
            "TEMPORARY_PROVIDER_ERROR",
            "Provider temporarily unavailable. Will retry later.",
            retryable=True,
        )
    if status_code == 403:
        return SendErrorInfo(
            "QUOTA_EXCEEDED",
            "Sending quota reached. Will retry later.",
            retryable=True,
        )
    if status_code == 401:
        return SendErrorInfo(
            "AUTH_EXPIRED",
            "Email account requires reconnection.",
            retryable=False,
        )
    if status_code in {400, 404, 422}:
        return SendErrorInfo(
            "PROVIDER_REJECTED",
            "Message was rejected by the provider.",
            retryable=False,
        )
    return SendErrorInfo(
        "UNKNOWN",
        "Send failed. Please try again later.",
        retryable=False,
    )


def retry_delay_seconds(attempt_count: int, settings) -> int:
    if attempt_count <= 1:
        return settings.campaign_retry_delay_1_seconds
    return settings.campaign_retry_delay_2_seconds
