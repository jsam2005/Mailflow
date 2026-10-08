"""MailFlow FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes import (
    auth,
    campaigns,
    contact_lists,
    contacts,
    email_accounts,
    health,
    imports,
    internal_workers,
    public,
    suppressions,
    system,
    template_assets,
    templates,
)
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger, setup_logging
from app.core.middleware import SecurityHeadersMiddleware
from app.db.session import SessionLocal
from app.services.auth_service import AuthService
from app.services.token_encryption_service import validate_token_encryption_key
from app.utils.storage_init import ensure_storage_dirs
from app.workers.scheduler import shutdown_scheduler, start_scheduler

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings.environment)
    logger.info(
        "app.startup",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )

    if settings.storage_provider == "local":
        ensure_storage_dirs(settings.storage_path)
    validate_token_encryption_key()

    # Development convenience only — never auto-create admin in production.
    if settings.is_development and settings.admin_email and settings.admin_password:
        db: Session = SessionLocal()
        try:
            AuthService(db).ensure_admin_user(
                name=settings.admin_name or "Admin",
                email=settings.admin_email,
                password=settings.admin_password,
            )
        finally:
            db.close()
    elif settings.is_production:
        logger.info("app.startup.admin_bootstrap_skipped", reason="production")

    if settings.local_scheduler_enabled:
        start_scheduler()
        logger.info("scheduler.mode", mode="local_apscheduler")
    else:
        logger.info("scheduler.mode", mode="serverless_cron")

    yield

    if settings.local_scheduler_enabled:
        shutdown_scheduler()
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()

    docs_url = None if settings.is_production else "/docs"
    redoc_url = None if settings.is_production else "/redoc"

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
    )

    application.add_middleware(SecurityHeadersMiddleware)

    if settings.allowed_host_list != ["*"]:
        application.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_host_list,
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    application.include_router(health.router)
    application.include_router(auth.router)
    application.include_router(contact_lists.router)
    application.include_router(contacts.router)
    application.include_router(imports.router)
    application.include_router(templates.router)
    application.include_router(template_assets.router)
    application.include_router(email_accounts.router)
    application.include_router(campaigns.router)
    application.include_router(system.router)
    application.include_router(suppressions.router)
    application.include_router(public.router)
    application.include_router(internal_workers.router)

    @application.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "message": exc.message,
                "code": exc.code,
                "details": exc.details or None,
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        safe_errors = []
        for err in exc.errors():
            item = dict(err)
            ctx = item.get("ctx")
            if isinstance(ctx, dict):
                item["ctx"] = {
                    key: (
                        str(value)
                        if not isinstance(value, (str, int, float, bool, type(None)))
                        else value
                    )
                    for key, value in ctx.items()
                }
            safe_errors.append(item)
        return JSONResponse(
            status_code=422,
            content={
                "error": "Validation failed",
                "message": "Validation failed",
                "code": "validation_error",
                "details": {"errors": safe_errors},
            },
        )

    @application.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", error_type=type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={
                "error": "An unexpected error occurred",
                "message": "An unexpected error occurred",
                "code": "internal_error",
                "details": None,
            },
        )

    return application


app = create_app()
