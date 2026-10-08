"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for MailFlow."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "MailFlow"
    app_version: str = "0.1.0"
    environment: str = "development"

    # Database
    database_url: str = "postgresql+psycopg2://mailflow:mailflow_secret@localhost:5432/mailflow"

    # Security
    jwt_secret: str = "change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(
        default=1440,
        validation_alias=AliasChoices(
            "ACCESS_TOKEN_EXPIRE_MINUTES",
            "JWT_EXPIRE_MINUTES",
            "jwt_expire_minutes",
        ),
    )
    token_encryption_key: str = "change-me-generate-a-fernet-key=="
    cron_secret: str = ""

    # URLs / CORS / hosts
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"
    cors_origins: str = ""
    allowed_hosts: str = "*"

    # Admin bootstrap (development only — never auto-create in production)
    admin_name: str = "Admin"
    admin_email: str = ""
    admin_password: str = ""

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = (
        "http://localhost:8000/api/v1/email-accounts/google/callback"
    )

    # Scheduler / workers
    enable_local_scheduler: bool | None = None
    reply_sync_interval_minutes: int = 5
    campaign_sender_interval_seconds: int = 15
    campaign_worker_interval_seconds: int = 5
    campaign_worker_batch_size: int = 5
    campaign_max_send_attempts: int = 3
    campaign_stale_sending_minutes: int = 10
    campaign_retry_delay_1_seconds: int = 300
    campaign_retry_delay_2_seconds: int = 900
    campaign_sending_enabled: bool = False
    campaign_test_recipient_allowlist: str = ""
    app_timezone: str = "Asia/Kolkata"

    # Storage
    storage_path: str = "./storage"
    storage_provider: str = "local"  # local | vercel_blob
    blob_read_write_token: str = ""

    # Business / compliance (required before real marketing sends)
    business_name: str = ""
    business_address: str = ""
    support_email: str = ""
    privacy_policy_url: str = ""
    terms_url: str = ""
    unsubscribe_base_url: str = ""
    unsubscribe_token_ttl_days: int = 90

    # Imports / templates
    max_import_file_mb: int = 10
    import_batch_size: int = 500
    max_template_image_mb: int = 5
    max_template_name_len: int = 150
    max_template_subject_len: int = 255
    max_template_html_bytes: int = 512_000
    max_template_text_bytes: int = 512_000

    # Email accounts
    test_email_hourly_limit: int = 10
    oauth_state_ttl_minutes: int = 10
    default_daily_send_limit: int = 100
    default_hourly_send_limit: int = 20
    default_min_delay_seconds: int = 30
    default_max_delay_seconds: int = 90

    # Auth rate limits (DB-backed)
    login_rate_limit_per_minute: int = 10

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        normalized = (value or "development").strip().lower()
        if normalized not in {"development", "test", "production"}:
            raise ValueError("ENVIRONMENT must be development, test, or production")
        return normalized

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        """Accept Neon/postgres URLs and ensure SQLAlchemy psycopg2 dialect."""
        url = (value or "").strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://") :]
        return url

    @model_validator(mode="after")
    def validate_production(self) -> Settings:
        if self.environment != "production":
            return self

        missing: list[str] = []
        if not self.database_url or "change-me" in self.database_url:
            missing.append("DATABASE_URL")
        host = urlparse(self.database_url).hostname or ""
        if host in {"localhost", "127.0.0.1"}:
            missing.append("DATABASE_URL (must not use localhost in production)")
        if not self.jwt_secret or self.jwt_secret.startswith("change-me"):
            missing.append("JWT_SECRET")
        if len(self.jwt_secret) < 32:
            missing.append("JWT_SECRET (min 32 characters)")
        if not self.token_encryption_key or self.token_encryption_key.startswith("change-me"):
            missing.append("TOKEN_ENCRYPTION_KEY")
        try:
            from cryptography.fernet import Fernet

            Fernet(self.token_encryption_key.encode())
        except Exception:
            missing.append("TOKEN_ENCRYPTION_KEY (invalid Fernet key)")
        if not self.google_client_id:
            missing.append("GOOGLE_CLIENT_ID")
        if not self.google_client_secret:
            missing.append("GOOGLE_CLIENT_SECRET")
        if not self.google_redirect_uri.startswith("https://"):
            missing.append("GOOGLE_REDIRECT_URI (must be HTTPS)")
        if not self.frontend_url.startswith("https://"):
            missing.append("FRONTEND_URL (must be HTTPS)")
        if not self.cron_secret or len(self.cron_secret) < 32:
            missing.append("CRON_SECRET (min 32 characters)")
        if self.storage_provider == "vercel_blob" and not self.blob_read_write_token:
            missing.append("BLOB_READ_WRITE_TOKEN")
        if self.storage_provider not in {"local", "vercel_blob"}:
            missing.append("STORAGE_PROVIDER (local|vercel_blob)")
        if self.enable_local_scheduler is True:
            missing.append("ENABLE_LOCAL_SCHEDULER must be false in production")

        if missing:
            raise ValueError(
                "Invalid production configuration: " + "; ".join(missing)
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def local_scheduler_enabled(self) -> bool:
        if self.enable_local_scheduler is not None:
            return bool(self.enable_local_scheduler)
        return self.environment == "development"

    @property
    def storage_root(self) -> Path:
        return Path(self.storage_path)

    @property
    def imports_path(self) -> Path:
        return self.storage_root / "imports"

    @property
    def max_import_file_bytes(self) -> int:
        return self.max_import_file_mb * 1024 * 1024

    @property
    def campaign_test_allowlist_emails(self) -> set[str]:
        if not self.campaign_test_recipient_allowlist.strip():
            return set()
        return {
            part.strip().lower()
            for part in self.campaign_test_recipient_allowlist.split(",")
            if part.strip()
        }

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip():
            return [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return [self.frontend_url]

    @property
    def allowed_host_list(self) -> list[str]:
        if not self.allowed_hosts.strip() or self.allowed_hosts.strip() == "*":
            return ["*"]
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def effective_unsubscribe_base_url(self) -> str:
        if self.unsubscribe_base_url.strip():
            return self.unsubscribe_base_url.rstrip("/")
        return self.frontend_url.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
