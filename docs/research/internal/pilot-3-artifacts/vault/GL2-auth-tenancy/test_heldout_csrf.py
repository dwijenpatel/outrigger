"""Held-out adversarial tests: CSRF protection on mutating POSTs.

Acceptance #4: any mutating POST without a valid csrf_token field -> 400 with
ZERO state change. Attacked here on the two unambiguously-authenticated
mutating endpoints (logout, settings): absent token, wrong token, and a token
belonging to a *different* session all -> 400, and the mutation does not happen.

(Signup/login carry the token in the helper's POST so they pass regardless of
whether pre-auth endpoints enforce CSRF; that reading is left to the operator.)
"""

from __future__ import annotations

import base64
import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone as _utc

import pytest
from fastapi.testclient import TestClient

from app.models import Base, Company, User


_TAG_RE = re.compile(r"<(input|select)\b[^>]*>", re.IGNORECASE)
_ATTR_RE = re.compile(r'([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*"([^"]*)"')


def _fields(html):
    out = []
    for m in _TAG_RE.finditer(html or ""):
        attrs = {k.lower(): v for k, v in _ATTR_RE.findall(m.group(0))}
        out.append((m.group(1).lower(), attrs))
    return out


def extract_csrf(html):
    for _, a in _fields(html):
        if a.get("name") == "csrf_token":
            return a.get("value", "")
    return None


def build_form(html, *, email=None, password=None, timezone=None, text="Acme Co", overrides=None):
    data = {}
    for kind, a in _fields(html):
        name = a.get("name")
        if not name:
            continue
        t = a.get("type", "text").lower()
        low = name.lower()
        if t == "hidden" or name == "csrf_token":
            data[name] = a.get("value", "")
        elif t == "password" or "password" in low or low == "pass":
            data[name] = "password123" if password is None else password
        elif t == "email" or "email" in low:
            data[name] = "user@example.com" if email is None else email
        elif kind == "select" or "timezone" in low or "tz" in low or "zone" in low:
            data[name] = "America/New_York" if timezone is None else timezone
        else:
            data[name] = text
    if overrides:
        data.update(overrides)
    return data


def location_path(resp):
    loc = resp.headers.get("location", "")
    for p in ("http://testserver", "https://testserver"):
        if loc.startswith(p):
            loc = loc[len(p):]
    return loc or "/"


@contextmanager
def db_session(app):
    Base.metadata.create_all(bind=app.state.engine)
    db = app.state.session_factory()
    try:
        yield db
    finally:
        db.close()


def make_user(app, *, email, password="password123", role="owner",
              company="Acme Co", name="Owner", timezone="America/New_York"):
    from app.security import hash_password

    with db_session(app) as db:
        c = Company(name=company, timezone=timezone, created_at=datetime.now(_utc.utc))
        db.add(c)
        db.commit()
        db.refresh(c)
        u = User(company_id=c.id, email=email.lower(),
                 password_hash=hash_password(password), role=role,
                 name=name, created_at=datetime.now(_utc.utc))
        db.add(u)
        db.commit()
        db.refresh(u)
        return c.id, u.id


def _get_then_post(client, path, **form):
    r = client.get(path)
    return client.post(path, data=build_form(r.text, **form), follow_redirects=False)


def login(client, *, email, password="password123"):
    return _get_then_post(client, "/login", email=email, password=password)


def owner_csrf(client):
    r = client.get("/settings")
    return extract_csrf(r.text) if r.status_code == 200 else None


def is_logged_in(client):
    """Authenticated GET / -> 200; unauthenticated -> 303 redirect to /login."""
    return client.get("/", follow_redirects=False).status_code == 200


# --------------------------------------------------------------------------- #
# Logout: absent / wrong token -> 400, session survives (no state change).
# --------------------------------------------------------------------------- #
def test_logout_without_csrf_is_400_and_session_survives(app):
    make_user(app, email="owner@example.com", role="owner", company="Acme Co")
    with TestClient(app) as c:
        assert login(c, email="owner@example.com").status_code == 303
        assert is_logged_in(c)

        resp = c.post("/logout", data={}, follow_redirects=False)
        assert resp.status_code == 400
        assert is_logged_in(c), "logout without CSRF must NOT clear the session"


def test_logout_with_wrong_csrf_is_400_and_session_survives(app):
    make_user(app, email="owner@example.com", role="owner", company="Acme Co")
    with TestClient(app) as c:
        assert login(c, email="owner@example.com").status_code == 303
        assert is_logged_in(c)

        resp = c.post("/logout", data={"csrf_token": "not-the-real-token"},
                      follow_redirects=False)
        assert resp.status_code == 400
        assert is_logged_in(c)


def test_logout_with_another_sessions_csrf_is_400(app):
    make_user(app, email="a@example.com", role="owner", company="Company A")
    make_user(app, email="b@example.com", role="owner", company="Company B")
    with TestClient(app) as ca, TestClient(app) as cb:
        assert login(ca, email="a@example.com").status_code == 303
        assert login(cb, email="b@example.com").status_code == 303

        foreign_token = owner_csrf(cb)
        assert foreign_token, "could not read session B's csrf token"

        resp = ca.post("/logout", data={"csrf_token": foreign_token},
                       follow_redirects=False)
        assert resp.status_code == 400, "a token from another session must be rejected"
        assert is_logged_in(ca), "rejected logout must not clear session A"


def test_logout_with_valid_csrf_succeeds(app):
    """Positive control: a valid token DOES log out -> 303 /login."""
    make_user(app, email="owner@example.com", role="owner", company="Acme Co")
    with TestClient(app) as c:
        assert login(c, email="owner@example.com").status_code == 303
        token = owner_csrf(c)
        assert token
        resp = c.post("/logout", data={"csrf_token": token}, follow_redirects=False)
        assert resp.status_code == 303
        assert location_path(resp) == "/login"
        assert not is_logged_in(c)


# --------------------------------------------------------------------------- #
# Settings: mutating POST without a valid token -> 400, company unchanged.
# --------------------------------------------------------------------------- #
def test_settings_post_without_csrf_is_400_and_no_mutation(app):
    cid, _uid = make_user(app, email="owner@example.com", role="owner",
                          company="Original Co")
    with TestClient(app) as c:
        assert login(c, email="owner@example.com").status_code == 303

        form_page = c.get("/settings")
        assert form_page.status_code == 200
        data = build_form(form_page.text, timezone="America/New_York",
                          text="HACKED CO")
        data.pop("csrf_token", None)  # strip the token -> must be rejected

        resp = c.post("/settings", data=data, follow_redirects=False)
        assert resp.status_code == 400

    with db_session(app) as db:
        company = db.query(Company).filter_by(id=cid).one()
        assert company.name == "Original Co", "settings mutated despite missing CSRF"


def test_settings_post_with_wrong_csrf_is_400_and_no_mutation(app):
    cid, _uid = make_user(app, email="owner@example.com", role="owner",
                          company="Original Co")
    with TestClient(app) as c:
        assert login(c, email="owner@example.com").status_code == 303

        form_page = c.get("/settings")
        assert form_page.status_code == 200
        data = build_form(form_page.text, timezone="America/New_York",
                          text="HACKED CO", overrides={"csrf_token": "bogus"})

        resp = c.post("/settings", data=data, follow_redirects=False)
        assert resp.status_code == 400

    with db_session(app) as db:
        company = db.query(Company).filter_by(id=cid).one()
        assert company.name == "Original Co"
