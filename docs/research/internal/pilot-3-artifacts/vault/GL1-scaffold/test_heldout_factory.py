"""Held-out tests: create_app() factory contract (GL1-scaffold spec).

Spec pins: create_app() -> FastAPI; mounts /static; configures a
Jinja2Templates instance on app.state.templates pointing at app/templates/.
"""

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates


def _fresh_app(tmp_path, monkeypatch, name="factory.db"):
    monkeypatch.setenv("GREENLANE_DB", f"sqlite:///{tmp_path / name}")
    from app import create_app

    return create_app()


def test_create_app_returns_fastapi_instance(tmp_path, monkeypatch):
    application = _fresh_app(tmp_path, monkeypatch)
    assert isinstance(application, FastAPI)


def test_create_app_returns_distinct_apps(tmp_path, monkeypatch):
    a = _fresh_app(tmp_path, monkeypatch, "a.db")
    b = _fresh_app(tmp_path, monkeypatch, "b.db")
    assert a is not b


def test_templates_configured_on_app_state(app):
    templates = app.state.templates
    assert isinstance(templates, Jinja2Templates)


def test_templates_loader_finds_base_html(app):
    # Pinned: Jinja2Templates points at app/templates/, which contains base.html.
    tmpl = app.state.templates.get_template("base.html")
    assert tmpl is not None


def test_static_mount_serves_styles_css(client):
    r = client.get("/static/styles.css")
    assert r.status_code == 200
    ctype = r.headers.get("content-type", "")
    assert "text/css" in ctype
    assert len(r.content) > 0


def test_static_mount_missing_file_is_404(client):
    r = client.get("/static/__heldout_does_not_exist__.css")
    assert r.status_code == 404
