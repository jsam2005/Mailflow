"""Email template CRUD and rendering orchestration."""

from __future__ import annotations

from math import ceil
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationAppError
from app.core.logging import get_logger
from app.models.contact import Contact
from app.models.contact_list import ContactList
from app.models.email_template import EmailTemplate
from app.models.user import User
from app.schemas.templates import (
    EmailTemplateCreate,
    EmailTemplateResponse,
    EmailTemplateUpdate,
    PaginatedTemplatesResponse,
    TemplatePreviewRequest,
    TemplateRenderResponse,
)
from app.services.template_render_service import (
    SAMPLE_PREVIEW_CONTEXT,
    RenderContext,
    TemplateRenderService,
)
from app.utils.html_sanitize import sanitize_email_html
from app.utils.plain_text import html_to_plain_text

logger = get_logger(__name__)

SORT_COLUMNS = {
    "created_at": EmailTemplate.created_at,
    "updated_at": EmailTemplate.updated_at,
    "name": EmailTemplate.name,
}


class TemplateService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.renderer = TemplateRenderService()

    def create(self, user: User, data: EmailTemplateCreate) -> EmailTemplateResponse:
        self._validate_sizes(data.name, data.subject, data.html_content, data.plain_text_content)
        html = sanitize_email_html(data.html_content)
        plain, customized = self._resolve_plain_text(
            html,
            data.plain_text_content,
            data.plain_text_customized,
        )
        template = EmailTemplate(
            user_id=user.id,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            subject=data.subject.strip(),
            html_content=html,
            plain_text_content=plain,
            plain_text_customized=customized,
            is_active=data.is_active,
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        logger.info("template.created", user_id=str(user.id), template_id=str(template.id))
        return self._to_response(template)

    def list_templates(
        self,
        user: User,
        *,
        page: int = 1,
        page_size: int = 25,
        search: str | None = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> PaginatedTemplatesResponse:
        filters = [EmailTemplate.user_id == user.id]
        if search:
            term = f"%{search.strip()}%"
            filters.append(
                or_(
                    EmailTemplate.name.ilike(term),
                    EmailTemplate.subject.ilike(term),
                    EmailTemplate.description.ilike(term),
                )
            )
        where_clause = and_(*filters)
        total = self.db.scalar(
            select(func.count()).select_from(EmailTemplate).where(where_clause)
        ) or 0
        column = SORT_COLUMNS.get(sort_by, EmailTemplate.updated_at)
        order = column.asc() if sort_order == "asc" else column.desc()
        items = list(
            self.db.scalars(
                select(EmailTemplate)
                .where(where_clause)
                .order_by(order, EmailTemplate.id.asc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()
        )
        return PaginatedTemplatesResponse(
            items=[self._to_response(item) for item in items],
            page=page,
            page_size=page_size,
            total=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get(self, user: User, template_id: UUID) -> EmailTemplateResponse:
        return self._to_response(self._get_owned(user, template_id))

    def update(
        self,
        user: User,
        template_id: UUID,
        data: EmailTemplateUpdate,
    ) -> EmailTemplateResponse:
        template = self._get_owned(user, template_id)
        name = data.name if data.name is not None else template.name
        subject = data.subject if data.subject is not None else template.subject
        html_raw = data.html_content if data.html_content is not None else template.html_content
        plain_raw = (
            data.plain_text_content
            if data.plain_text_content is not None
            else template.plain_text_content
        )
        self._validate_sizes(name, subject, html_raw, plain_raw)

        if data.name is not None:
            template.name = data.name.strip()
        if data.description is not None:
            template.description = data.description.strip() or None
        if data.subject is not None:
            template.subject = data.subject.strip()
        if data.html_content is not None:
            template.html_content = sanitize_email_html(data.html_content)
        if data.is_active is not None:
            template.is_active = data.is_active

        customized = (
            data.plain_text_customized
            if data.plain_text_customized is not None
            else template.plain_text_customized
        )
        if data.plain_text_content is not None or data.html_content is not None or data.plain_text_customized is not None:
            plain, customized = self._resolve_plain_text(
                template.html_content,
                data.plain_text_content if data.plain_text_content is not None else template.plain_text_content,
                customized,
                force_regen=data.html_content is not None and not customized,
            )
            template.plain_text_content = plain
            template.plain_text_customized = customized

        self.db.commit()
        self.db.refresh(template)
        logger.info("template.updated", user_id=str(user.id), template_id=str(template.id))
        return self._to_response(template)

    def delete(self, user: User, template_id: UUID) -> None:
        template = self._get_owned(user, template_id)
        self.db.delete(template)
        self.db.commit()
        logger.info("template.deleted", user_id=str(user.id), template_id=str(template_id))

    def duplicate(self, user: User, template_id: UUID) -> EmailTemplateResponse:
        source = self._get_owned(user, template_id)
        new_name = self._unique_copy_name(user, source.name)
        copy = EmailTemplate(
            user_id=user.id,
            name=new_name,
            description=source.description,
            subject=source.subject,
            html_content=source.html_content,
            plain_text_content=source.plain_text_content,
            plain_text_customized=source.plain_text_customized,
            is_active=source.is_active,
        )
        self.db.add(copy)
        self.db.commit()
        self.db.refresh(copy)
        logger.info(
            "template.duplicated",
            user_id=str(user.id),
            source_id=str(template_id),
            template_id=str(copy.id),
        )
        return self._to_response(copy)

    def render_template(
        self,
        user: User,
        template_id: UUID,
        contact_id: UUID | None = None,
        sample_data: dict | None = None,
    ) -> TemplateRenderResponse:
        template = self._get_owned(user, template_id)
        return self._render(
            user,
            subject=template.subject,
            html_content=template.html_content,
            plain_text_content=template.plain_text_content,
            contact_id=contact_id,
            sample_data=sample_data,
        )

    def render_preview(
        self,
        user: User,
        data: TemplatePreviewRequest,
    ) -> TemplateRenderResponse:
        self._validate_sizes(data.subject[:150], data.subject, data.html_content, data.plain_text_content)
        html = sanitize_email_html(data.html_content)
        return self._render(
            user,
            subject=data.subject.strip(),
            html_content=html,
            plain_text_content=data.plain_text_content,
            contact_id=data.contact_id,
            sample_data=data.sample_data,
        )

    def _render(
        self,
        user: User,
        *,
        subject: str,
        html_content: str,
        plain_text_content: str | None,
        contact_id: UUID | None,
        sample_data: dict | None,
    ) -> TemplateRenderResponse:
        preview_mode = "sample"
        if contact_id:
            context = self._context_from_contact(user, contact_id)
            preview_mode = "contact"
        elif sample_data:
            context = self._context_from_sample(sample_data)
        else:
            context = SAMPLE_PREVIEW_CONTEXT

        result = self.renderer.render(
            subject=subject,
            html_content=html_content,
            plain_text_content=plain_text_content,
            context=context,
            escape_html_values=True,
        )
        # Sanitize again after interpolation (defense in depth; values already escaped)
        rendered_html = sanitize_email_html(result.rendered_html)
        return TemplateRenderResponse(
            rendered_subject=result.rendered_subject,
            rendered_html=rendered_html,
            rendered_text=result.rendered_text,
            warnings=result.warnings,
            used_variables=result.used_variables,
            missing_variables=result.missing_variables,
            preview_mode=preview_mode,
        )

    def _context_from_contact(self, user: User, contact_id: UUID) -> RenderContext:
        stmt = (
            select(Contact)
            .join(ContactList, Contact.contact_list_id == ContactList.id)
            .where(Contact.id == contact_id, ContactList.user_id == user.id)
        )
        contact = self.db.scalar(stmt)
        if contact is None:
            raise NotFoundError("Contact not found")
        return RenderContext(
            first_name=contact.first_name,
            last_name=contact.last_name,
            company=contact.company,
            email=contact.email,
            phone=contact.phone,
            website=contact.website,
            metadata=contact.contact_metadata or {},
        )

    @staticmethod
    def _context_from_sample(data: dict) -> RenderContext:
        meta = data.get("metadata") or data.get("meta") or {}
        if not isinstance(meta, dict):
            meta = {}
        return RenderContext(
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            company=data.get("company"),
            email=data.get("email"),
            phone=data.get("phone"),
            website=data.get("website"),
            metadata=meta,
        )

    def _get_owned(self, user: User, template_id: UUID) -> EmailTemplate:
        template = self.db.scalar(
            select(EmailTemplate).where(
                EmailTemplate.id == template_id,
                EmailTemplate.user_id == user.id,
            )
        )
        if template is None:
            raise NotFoundError("Template not found")
        return template

    def _unique_copy_name(self, user: User, base_name: str) -> str:
        candidate = f"{base_name} Copy"
        existing = set(
            self.db.scalars(
                select(EmailTemplate.name).where(EmailTemplate.user_id == user.id)
            ).all()
        )
        if candidate not in existing:
            return candidate[:150]
        index = 2
        while True:
            candidate = f"{base_name} Copy {index}"
            if candidate not in existing:
                return candidate[:150]
            index += 1

    def _validate_sizes(
        self,
        name: str,
        subject: str,
        html_content: str | None,
        plain_text: str | None,
    ) -> None:
        if len(name) > self.settings.max_template_name_len:
            raise ValidationAppError("Template name is too long")
        if len(subject) > self.settings.max_template_subject_len:
            raise ValidationAppError("Subject is too long")
        if html_content and len(html_content.encode("utf-8")) > self.settings.max_template_html_bytes:
            raise ValidationAppError("HTML content exceeds the size limit")
        if plain_text and len(plain_text.encode("utf-8")) > self.settings.max_template_text_bytes:
            raise ValidationAppError("Plain text content exceeds the size limit")
        if not (html_content or "").strip():
            raise ValidationAppError("HTML content is required")
        if not subject.strip():
            raise ValidationAppError("Subject is required")

    def _resolve_plain_text(
        self,
        html: str,
        plain: str | None,
        customized: bool,
        force_regen: bool = False,
    ) -> tuple[str, bool]:
        if customized and plain is not None and not force_regen:
            return plain, True
        if plain and plain.strip() and customized:
            return plain, True
        return html_to_plain_text(html), False

    def _to_response(self, template: EmailTemplate) -> EmailTemplateResponse:
        warnings = []
        variables = self.renderer.extract_variables(
            template.subject,
            template.html_content,
            template.plain_text_content or "",
        )
        for var in variables:
            if var.startswith("meta."):
                continue
            if var not in {
                "first_name",
                "last_name",
                "full_name",
                "company",
                "email",
                "phone",
                "website",
            }:
                warnings.append(f"Unknown variable: {var}")
        if not variables:
            warnings.append("No personalization variables used")
        if len(template.subject) > 120:
            warnings.append("Very long subject")
        if not template.plain_text_content:
            warnings.append("Missing plain text fallback")

        return EmailTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            subject=template.subject,
            html_content=template.html_content,
            plain_text_content=template.plain_text_content,
            plain_text_customized=template.plain_text_customized,
            is_active=template.is_active,
            created_at=template.created_at,
            updated_at=template.updated_at,
            warnings=warnings,
        )
