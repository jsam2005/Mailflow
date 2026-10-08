# Phase 4 — Email templates

## Architecture

- `EmailTemplate` owned by user
- `TemplateAsset` tracks uploaded images under `storage/template-images/`
- Safe custom renderer (`TemplateRenderService`) — no Jinja/eval
- HTML sanitized with `bleach` on write and before preview
- TipTap editor on the frontend; backend remains source of truth for render

## Personalization

| Syntax | Meaning |
|--------|---------|
| `{{first_name}}` | Contact first name |
| `{{last_name}}` | Contact last name |
| `{{full_name}}` | Derived first + last |
| `{{company}}` | Company |
| `{{email}}` | Email |
| `{{phone}}` | Phone |
| `{{website}}` | Website |
| `{{meta.city}}` | Custom metadata key |
| `{{first_name\|there}}` | Fallback when missing |

Contact values are **HTML-escaped** when injected into HTML.

## Plain text

Auto-generated from HTML with BeautifulSoup unless `plain_text_customized=true`.

## Images

Allowed: JPEG, PNG, WEBP, GIF (no SVG). Max `MAX_TEMPLATE_IMAGE_MB` (default 5).

Editor markup:

```html
<img
  src="/api/v1/template-assets/{id}/content?access_token=..."
  data-mailflow-asset-id="{id}"
  alt=""
/>
```

`content_id` / `cid:` placeholders are stored for future MIME sending.

**Limitation:** localhost image URLs do not load for external recipients. Later phases attach CID inline images.

## APIs

Templates: list/create/get/update/delete/duplicate/render + `POST /templates/render-preview`

Assets: `POST /template-assets`, `GET /template-assets/{id}/content`

## Duplicate naming

`Name` → `Name Copy` → `Name Copy 2` …

Assets are not copied; HTML may still reference prior asset IDs owned by the same user.
