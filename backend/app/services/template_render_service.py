"""Safe personalization rendering for email templates."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Any

VARIABLE_PATTERN = re.compile(
    r"\{\{\s*([a-zA-Z_][\w.]*)(?:\|([^}]*))?\s*\}\}"
)

BUILTIN_FIELDS = {
    "first_name",
    "last_name",
    "full_name",
    "company",
    "email",
    "phone",
    "website",
}


@dataclass
class RenderContext:
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    email: str | None = None
    phone: str | None = None
    website: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def full_name(self) -> str | None:
        parts = [p for p in [self.first_name, self.last_name] if p and str(p).strip()]
        if not parts:
            return None
        return " ".join(str(p).strip() for p in parts)


@dataclass
class RenderResult:
    rendered_subject: str
    rendered_html: str
    rendered_text: str
    warnings: list[str]
    used_variables: list[str]
    missing_variables: list[str]


class TemplateRenderService:
    @staticmethod
    def has_unresolved_tokens(*texts: str | None) -> bool:
        """True if any {{variable}} token remains (malformed or unprocessed)."""
        for text in texts:
            if text and VARIABLE_PATTERN.search(text):
                return True
        return False

    def render(
        self,
        *,
        subject: str,
        html_content: str,
        plain_text_content: str | None,
        context: RenderContext,
        escape_html_values: bool = True,
    ) -> RenderResult:
        warnings: list[str] = []
        used: set[str] = set()
        missing: set[str] = set()

        rendered_subject = self._render_string(
            subject,
            context,
            escape_html=False,
            warnings=warnings,
            used=used,
            missing=missing,
        )
        rendered_html = self._render_string(
            html_content,
            context,
            escape_html=escape_html_values,
            warnings=warnings,
            used=used,
            missing=missing,
        )

        if plain_text_content and plain_text_content.strip():
            rendered_text = self._render_string(
                plain_text_content,
                context,
                escape_html=False,
                warnings=warnings,
                used=used,
                missing=missing,
            )
        else:
            from app.utils.plain_text import html_to_plain_text

            rendered_text = html_to_plain_text(rendered_html)

        return RenderResult(
            rendered_subject=rendered_subject,
            rendered_html=rendered_html,
            rendered_text=rendered_text,
            warnings=sorted(set(warnings)),
            used_variables=sorted(used),
            missing_variables=sorted(missing),
        )

    def extract_variables(self, *texts: str) -> list[str]:
        found: set[str] = set()
        for text in texts:
            for match in VARIABLE_PATTERN.finditer(text or ""):
                found.add(match.group(1))
        return sorted(found)

    def _render_string(
        self,
        template: str,
        context: RenderContext,
        *,
        escape_html: bool,
        warnings: list[str],
        used: set[str],
        missing: set[str],
    ) -> str:
        def replacer(match: re.Match[str]) -> str:
            name = match.group(1)
            fallback = match.group(2)
            fallback_value = fallback.strip() if fallback is not None else ""
            value = self._resolve(name, context, warnings)
            used.add(name)
            if value is None or str(value).strip() == "":
                missing.add(name)
                value = fallback_value
            text = "" if value is None else str(value)
            return html.escape(text, quote=True) if escape_html else text

        return VARIABLE_PATTERN.sub(replacer, template or "")

    def _resolve(
        self,
        name: str,
        context: RenderContext,
        warnings: list[str],
    ) -> Any:
        if name.startswith("meta."):
            key = name[5:]
            if not key:
                warnings.append(f"Unknown variable: {name}")
                return None
            meta = context.metadata or {}
            if key not in meta:
                return None
            return meta.get(key)

        if name in BUILTIN_FIELDS:
            if name == "full_name":
                return context.full_name
            return getattr(context, name, None)

        warnings.append(f"Unknown variable: {name}")
        return None


SAMPLE_PREVIEW_CONTEXT = RenderContext(
    first_name="Arun",
    last_name="Kumar",
    company="Example Business",
    email="arun@example.com",
    phone="9876543210",
    website="https://example.com",
    metadata={"city": "Chennai", "industry": "Construction"},
)
