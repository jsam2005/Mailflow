"""Email template and asset tests."""

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image


def _auth_create_template(client: TestClient, headers: dict[str, str], **overrides: object) -> dict:
    payload = {
        "name": "Website Outreach",
        "description": "Local outreach",
        "subject": "Quick idea for {{company|your business}}",
        "html_content": "<p>Hi {{first_name|there}},</p><p>I came across {{company|your business}}.</p>",
        "plain_text_content": None,
        "plain_text_customized": False,
    }
    payload.update(overrides)
    response = client.post("/api/v1/templates", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _png_bytes(color: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 24), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_create_list_search_update_delete(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    created = _auth_create_template(client, auth_headers)
    assert created["name"] == "Website Outreach"
    assert "<script>" not in created["html_content"]

    listed = client.get("/api/v1/templates", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    search = client.get(
        "/api/v1/templates",
        headers=auth_headers,
        params={"search": "Website"},
    )
    assert search.json()["total"] == 1

    updated = client.put(
        f"/api/v1/templates/{created['id']}",
        headers=auth_headers,
        json={"name": "Updated Outreach"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Updated Outreach"

    deleted = client.delete(f"/api/v1/templates/{created['id']}", headers=auth_headers)
    assert deleted.status_code == 204


def test_duplicate_template(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = _auth_create_template(client, auth_headers)
    dup = client.post(
        f"/api/v1/templates/{created['id']}/duplicate",
        headers=auth_headers,
    )
    assert dup.status_code == 200
    assert dup.json()["name"] == "Website Outreach Copy"
    assert dup.json()["id"] != created["id"]

    dup2 = client.post(
        f"/api/v1/templates/{created['id']}/duplicate",
        headers=auth_headers,
    )
    assert dup2.json()["name"] == "Website Outreach Copy 2"


def test_ownership_isolation(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    created = _auth_create_template(client, auth_headers)
    response = client.get(
        f"/api/v1/templates/{created['id']}",
        headers=other_auth_headers,
    )
    assert response.status_code == 404


def test_html_sanitization_strips_scripts_and_handlers(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    created = _auth_create_template(
        client,
        auth_headers,
        html_content=(
            '<p>Hello</p><script>alert(1)</script>'
            '<img src="x" onerror="alert(1)" alt="x">'
            '<a href="javascript:alert(1)">bad</a>'
            '<a href="https://example.com">good</a>'
        ),
    )
    html = created["html_content"]
    assert "<script>" not in html.lower()
    assert "onerror" not in html.lower()
    assert "javascript:" not in html.lower()
    assert "https://example.com" in html


def test_render_personalization_and_escaping(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    # Create list + contact with malicious first name
    listing = client.post(
        "/api/v1/contact-lists",
        headers=auth_headers,
        json={"name": "Preview List"},
    ).json()
    contact = client.post(
        f"/api/v1/contact-lists/{listing['id']}/contacts",
        headers=auth_headers,
        json={
            "email": "arun@example.com",
            "first_name": '<script>alert("x")</script>',
            "last_name": "Kumar",
            "company": "Acme",
            "metadata": {"city": "Chennai"},
        },
    ).json()

    template = _auth_create_template(
        client,
        auth_headers,
        subject="Hello {{first_name|there}} at {{company|your business}}",
        html_content=(
            "<p>Hi {{first_name|there}},</p>"
            "<p>{{full_name}} from {{meta.city|your area}}</p>"
            "<p>{{unknown_field}}</p>"
        ),
    )

    rendered = client.post(
        f"/api/v1/templates/{template['id']}/render",
        headers=auth_headers,
        json={"contact_id": contact["id"]},
    )
    assert rendered.status_code == 200, rendered.text
    body = rendered.json()
    assert "&lt;script&gt;" in body["rendered_html"]
    assert "<script>" not in body["rendered_html"]
    assert "Acme" in body["rendered_subject"] or "Acme" in body["rendered_html"]
    assert "Chennai" in body["rendered_html"]
    assert any("unknown_field" in w for w in body["warnings"])
    assert "Kumar" in body["rendered_html"]


def test_fallback_and_sample_preview(client: TestClient, auth_headers: dict[str, str]) -> None:
    preview = client.post(
        "/api/v1/templates/render-preview",
        headers=auth_headers,
        json={
            "subject": "Hi {{first_name|there}}",
            "html_content": "<p>Hello {{first_name|there}} at {{company|your business}}</p>",
            "sample_data": {},
        },
    )
    assert preview.status_code == 200
    # empty sample falls back to built-in sample context when sample_data empty?
    # Our service uses SAMPLE when no contact and no useful sample - empty dict still uses sample_data path
    # With empty sample_data keys missing → fallbacks
    body = preview.json()
    assert "there" in body["rendered_html"] or "Arun" in body["rendered_html"]


def test_plain_text_auto_generation(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = _auth_create_template(
        client,
        auth_headers,
        html_content="<p>Hello <strong>world</strong></p><p><a href='https://x.com'>Link</a></p>",
        plain_text_content=None,
        plain_text_customized=False,
    )
    assert created["plain_text_content"]
    assert "<p>" not in created["plain_text_content"]
    assert "Hello" in created["plain_text_content"]


def test_asset_upload_and_ownership(
    client: TestClient,
    auth_headers: dict[str, str],
    other_auth_headers: dict[str, str],
) -> None:
    upload = client.post(
        "/api/v1/template-assets",
        headers=auth_headers,
        files={"file": ("logo.png", _png_bytes(), "image/png")},
    )
    assert upload.status_code == 201, upload.text
    asset = upload.json()
    assert asset["mime_type"] == "image/png"
    assert asset["width"] == 32
    assert asset["content_id"]
    assert asset["cid_placeholder"].startswith("cid:")

    content = client.get(
        f"/api/v1/template-assets/{asset['id']}/content",
        headers=auth_headers,
    )
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("image/")

    denied = client.get(
        f"/api/v1/template-assets/{asset['id']}/content",
        headers=other_auth_headers,
    )
    assert denied.status_code == 404


def test_reject_unsupported_and_oversized_image(
    client: TestClient,
    auth_headers: dict[str, str],
    monkeypatch,
) -> None:
    bad = client.post(
        "/api/v1/template-assets",
        headers=auth_headers,
        files={"file": ("x.svg", b"<svg></svg>", "image/svg+xml")},
    )
    assert bad.status_code == 422

    malformed = client.post(
        "/api/v1/template-assets",
        headers=auth_headers,
        files={"file": ("x.png", b"not-an-image", "image/png")},
    )
    assert malformed.status_code == 422

    import app.services.template_asset_service as asset_module
    from app.core.config import Settings

    monkeypatch.setattr(asset_module, "get_settings", lambda: Settings(max_template_image_mb=0))
    oversized = client.post(
        "/api/v1/template-assets",
        headers=auth_headers,
        files={"file": ("big.png", _png_bytes(), "image/png")},
    )
    assert oversized.status_code == 422


def test_unit_sanitize_and_render() -> None:
    from app.services.template_render_service import RenderContext, TemplateRenderService
    from app.utils.html_sanitize import sanitize_email_html

    cleaned = sanitize_email_html('<p onclick="x">Hi</p><iframe src="x"></iframe>')
    assert "onclick" not in cleaned
    assert "iframe" not in cleaned

    result = TemplateRenderService().render(
        subject="{{first_name|there}}",
        html_content="<p>{{first_name}}</p>",
        plain_text_content=None,
        context=RenderContext(first_name='<b>Arun</b>'),
    )
    assert "&lt;b&gt;Arun&lt;/b&gt;" in result.rendered_html
