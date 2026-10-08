"""Email-safe HTML sanitization."""

from __future__ import annotations

import bleach
from bleach.css_sanitizer import CSSSanitizer

ALLOWED_TAGS = [
    "p",
    "div",
    "span",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "h1",
    "h2",
    "h3",
    "ul",
    "ol",
    "li",
    "a",
    "img",
    "table",
    "tbody",
    "thead",
    "tr",
    "td",
    "th",
    "blockquote",
    "hr",
]

ALLOWED_ATTRIBUTES = {
    "*": ["class", "style", "title"],
    "a": ["href", "target", "rel", "title"],
    "img": [
        "src",
        "alt",
        "title",
        "width",
        "height",
        "data-mailflow-asset-id",
    ],
    "td": ["colspan", "rowspan", "align", "valign"],
    "th": ["colspan", "rowspan", "align", "valign"],
    "p": ["align"],
    "div": ["align"],
}

ALLOWED_PROTOCOLS = ["http", "https", "mailto", "cid"]

CSS_SANITIZER = CSSSanitizer(
    allowed_css_properties=[
        "color",
        "background-color",
        "font-size",
        "font-weight",
        "font-style",
        "text-align",
        "text-decoration",
        "margin",
        "margin-top",
        "margin-bottom",
        "margin-left",
        "margin-right",
        "padding",
        "padding-top",
        "padding-bottom",
        "padding-left",
        "padding-right",
        "width",
        "max-width",
        "height",
        "line-height",
        "border",
        "border-collapse",
    ]
)


def sanitize_email_html(html: str) -> str:
    cleaned = bleach.clean(
        html or "",
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        css_sanitizer=CSS_SANITIZER,
        strip=True,
    )
    return cleaned
