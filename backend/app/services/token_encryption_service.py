"""Encrypt/decrypt OAuth tokens at rest with Fernet."""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.exceptions import ValidationAppError

# Deterministic valid Fernet key used only when ENVIRONMENT=test and key is invalid.
_TEST_FERNET_KEY = b"I_1WmUSBsquzW12HDIFVXjBnygdlDdlF82xrmaualtU="


class TokenEncryptionService:
    def __init__(self, key: str | None = None) -> None:
        settings = get_settings()
        raw = key if key is not None else settings.token_encryption_key
        self._fernet = self._build_fernet(raw, environment=settings.environment)

    @staticmethod
    def _build_fernet(raw: str | bytes | None, *, environment: str) -> Fernet:
        if not raw or (isinstance(raw, str) and raw.startswith("change-me")):
            if environment == "test":
                return Fernet(_TEST_FERNET_KEY)
            raise RuntimeError(
                "TOKEN_ENCRYPTION_KEY must be set to a valid Fernet key. "
                'Generate with: python -c "from cryptography.fernet import Fernet; '
                'print(Fernet.generate_key().decode())"'
            )
        try:
            key_bytes = raw.encode("utf-8") if isinstance(raw, str) else raw
            return Fernet(key_bytes)
        except Exception as exc:  # noqa: BLE001
            if environment == "test":
                return Fernet(_TEST_FERNET_KEY)
            raise RuntimeError(
                "TOKEN_ENCRYPTION_KEY is invalid. Generate a Fernet key with cryptography.fernet."
            ) from exc

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            raise ValidationAppError("Cannot encrypt empty token")
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            raise ValidationAppError("Missing encrypted token")
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValidationAppError("Unable to decrypt stored token") from exc


@lru_cache
def get_token_encryption() -> TokenEncryptionService:
    return TokenEncryptionService()


def validate_token_encryption_key() -> None:
    """Fail fast at startup when encryption key is missing/invalid outside tests."""
    settings = get_settings()
    TokenEncryptionService._build_fernet(
        settings.token_encryption_key,
        environment=settings.environment,
    )
