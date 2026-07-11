"""Held-out tests: base.html + asset rule (GL1-scaffold spec).

Spec pins:
- base.html: viewport meta, one content block named `content`, links
  styles.css; must render.
- Asset rule (project-wide): templates never reference external URLs --
  no CDN scripts, stylesheets, fonts, or images.
- ALL styling in styles.css with design tokens (CSS custom properties)
  at :root.
"""

import re
from pathlib import Path

import app as app_pkg
from fastapi.responses import HTMLResponse

APP_DIR = Path(app_pkg.__file__).resolve().parent
TEMPLATES_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"


def _base_src() -> str:
    return (TEMPLATES_DIR / "base.html").read_text()


# ---------------------------------------------------------------------------
# static (source-level) contract
# ---------------------------------------------------------------------------


def test_base_html_declares_content_block():
    assert re.search(r"\{%-?\s*block\s+content\s*(?:-?%\})", _base_src()), (
        "base.html must declare a Jinja block named exactly 'content'"
    )


def test_base_html_has_viewport_meta():
    assert re.search(
        r"<meta[^>]*name\s*=\s*[\"']viewport[\"']", _base_src(), re.I
    ), "base.html must include a viewport meta tag (responsive/phone-width)"


def test_base_html_references_styles_css():
    assert "styles.css" in _base_src()


def test_no_external_urls_in_templates_or_css():
    files = list(TEMPLATES_DIR.rglob("*.html")) + list(STATIC_DIR.rglob("*.css"))
    assert files, "expected at least base.html and styles.css to exist"
    offenders = []
    for f in files:
        text = f.read_text()
        if "http://" in text or "https://" in text:
            offenders.append((str(f), "absolute http(s) URL"))
        if re.search(r"(?:href|src)\s*=\s*[\"']//", text):
            offenders.append((str(f), "protocol-relative URL"))
        if re.search(r"url\(\s*[\"']?//", text):
            offenders.append((str(f), "protocol-relative CSS url()"))
        if re.search(r"@import\s+[\"']?(?:https?:)?//", text):
            offenders.append((str(f), "external @import"))
    assert not offenders, f"external references found: {offenders}"


def test_styles_css_defines_design_tokens_at_root():
    css = (STATIC_DIR / "styles.css").read_text()
    assert ":root" in css, "styles.css must define design tokens at :root"
    assert re.search(r"--[\w-]+\s*:", css), (
        "styles.css must define CSS custom properties (design tokens)"
    )


# ---------------------------------------------------------------------------
# rendered contract (through the app's own Jinja2Templates instance)
# ---------------------------------------------------------------------------


def _template_response(templates, request, name):
    try:
        # starlette >= 0.29 signature
        return templates.TemplateResponse(request, name)
    except Exception:
        # legacy signature
        return templates.TemplateResponse(name, {"request": request})


def test_base_html_renders_over_http(app, client):
    from fastapi import Request

    templates = app.state.templates

    @app.get("/__heldout_render_base")
    def render_base(request: Request):
        return _template_response(templates, request, "base.html")

    r = client.get("/__heldout_render_base")
    assert r.status_code == 200
    body = r.text
    assert re.search(r"<meta[^>]*name\s*=\s*[\"']viewport[\"']", body, re.I)
    assert "styles.css" in body


def test_child_template_fills_content_block(app, client):
    from fastapi import Request

    templates = app.state.templates
    marker = "HELDOUT-CONTENT-MARKER-7f3a"
    child_src = (
        '{% extends "base.html" %}'
        "{% block content %}" + marker + "{% endblock %}"
    )

    @app.get("/__heldout_render_child")
    def render_child(request: Request):
        tmpl = templates.env.from_string(child_src)
        html = tmpl.render({"request": request})
        return HTMLResponse(html)

    r = client.get("/__heldout_render_child")
    assert r.status_code == 200
    assert marker in r.text, (
        "a child template extending base.html and overriding block "
        "'content' must have its content rendered"
    )
    # The child's content must appear inside the base layout, not instead of it
    assert re.search(r"<meta[^>]*name\s*=\s*[\"']viewport[\"']", r.text, re.I)
