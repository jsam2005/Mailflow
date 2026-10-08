"""Application-level exceptions and HTTP mapping."""

from typing import Any


class AppError(Exception):
    """Base application error with a client-safe message."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        code: str = "app_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", **kwargs: Any) -> None:
        super().__init__(message, status_code=404, code="not_found", **kwargs)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required", **kwargs: Any) -> None:
        super().__init__(message, status_code=401, code="unauthorized", **kwargs)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied", **kwargs: Any) -> None:
        super().__init__(message, status_code=403, code="forbidden", **kwargs)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict", **kwargs: Any) -> None:
        super().__init__(message, status_code=409, code="conflict", **kwargs)


class ValidationAppError(AppError):
    def __init__(self, message: str = "Validation failed", **kwargs: Any) -> None:
        super().__init__(message, status_code=422, code="validation_error", **kwargs)


class RateLimitError(AppError):
    def __init__(self, message: str = "Rate limit exceeded", **kwargs: Any) -> None:
        super().__init__(message, status_code=429, code="rate_limit_exceeded", **kwargs)


class OAuthError(AppError):
    def __init__(self, message: str = "OAuth failed", **kwargs: Any) -> None:
        super().__init__(message, status_code=400, code="oauth_error", **kwargs)


class ServiceUnavailableError(AppError):
    def __init__(
        self,
        message: str = "Service unavailable",
        **kwargs: Any,
    ) -> None:
        super().__init__(message, status_code=503, code="service_unavailable", **kwargs)
