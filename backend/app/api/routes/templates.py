"""Email template API routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.templates import (
    EmailTemplateCreate,
    EmailTemplateResponse,
    EmailTemplateUpdate,
    PaginatedTemplatesResponse,
    TemplatePreviewRequest,
    TemplateRenderRequest,
    TemplateRenderResponse,
)
from app.services.template_service import TemplateService

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.post("/render-preview", response_model=TemplateRenderResponse)
def render_preview(
    body: TemplatePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateRenderResponse:
    return TemplateService(db).render_preview(current_user, body)


@router.get("", response_model=PaginatedTemplatesResponse)
def list_templates(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="updated_at"),
    sort_order: str = Query(default="desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedTemplatesResponse:
    if sort_by not in {"created_at", "updated_at", "name"}:
        sort_by = "updated_at"
    if sort_order.lower() not in {"asc", "desc"}:
        sort_order = "desc"
    return TemplateService(db).list_templates(
        current_user,
        page=page,
        page_size=page_size,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order.lower(),
    )


@router.post("", response_model=EmailTemplateResponse, status_code=201)
def create_template(
    body: EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmailTemplateResponse:
    return TemplateService(db).create(current_user, body)


@router.get("/{template_id}", response_model=EmailTemplateResponse)
def get_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmailTemplateResponse:
    return TemplateService(db).get(current_user, template_id)


@router.put("/{template_id}", response_model=EmailTemplateResponse)
def update_template(
    template_id: UUID,
    body: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmailTemplateResponse:
    return TemplateService(db).update(current_user, template_id, body)


@router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    TemplateService(db).delete(current_user, template_id)


@router.post("/{template_id}/duplicate", response_model=EmailTemplateResponse)
def duplicate_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EmailTemplateResponse:
    return TemplateService(db).duplicate(current_user, template_id)


@router.post("/{template_id}/render", response_model=TemplateRenderResponse)
def render_template(
    template_id: UUID,
    body: TemplateRenderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TemplateRenderResponse:
    return TemplateService(db).render_template(
        current_user,
        template_id,
        contact_id=body.contact_id,
        sample_data=body.sample_data,
    )
