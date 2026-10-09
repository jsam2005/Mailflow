"""Campaign message personalization helpers."""

from __future__ import annotations

from app.core.exceptions import ValidationAppError
from app.models.contact import Contact
from app.models.email_message import EmailMessage
from app.services.template_render_service import RenderContext, RenderResult, TemplateRenderService


class UnresolvedPersonalizationError(ValidationAppError):
    """Raised when template tokens remain after rendering."""

    def __init__(self, message: str = "Message contains unresolved personalization tokens.") -> None:
        super().__init__(message)


def contact_render_context(contact: Contact | None, *, fallback_email: str | None = None) -> RenderContext:
    return RenderContext(
        first_name=contact.first_name if contact else None,
        last_name=contact.last_name if contact else None,
        company=contact.company if contact else None,
        email=(contact.email if contact else None) or fallback_email,
        phone=contact.phone if contact else None,
        website=contact.website if contact else None,
        metadata=(contact.contact_metadata if contact else None) or {},
    )


def render_campaign_content(
    *,
    subject: str,
    html: str,
    text: str | None,
    contact: Contact | None,
    fallback_email: str | None = None,
    require_resolved: bool = True,
) -> RenderResult:
    renderer = TemplateRenderService()
    result = renderer.render(
        subject=subject or "",
        html_content=html or "",
        plain_text_content=text,
        context=contact_render_context(contact, fallback_email=fallback_email),
    )
    if require_resolved and TemplateRenderService.has_unresolved_tokens(
        result.rendered_subject,
        result.rendered_html,
        result.rendered_text,
    ):
        raise UnresolvedPersonalizationError()
    return result


def apply_render_to_message(message: EmailMessage, rendered: RenderResult) -> None:
    """Update stored rendered fields. Caller must not apply to sent messages."""
    message.subject = rendered.rendered_subject
    message.rendered_html = rendered.rendered_html
    message.rendered_text = rendered.rendered_text
