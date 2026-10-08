"""Shared API response schemas."""

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    database: str | None = None
    version: str | None = None


class ErrorResponse(BaseModel):
    error: str
    code: str
    details: dict[str, Any] | None = None
    message: str | None = None
