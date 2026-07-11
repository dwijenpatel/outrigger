"""Held-out adversarial tests: login, sessions, roles, auth gating.

Attacks acceptance #2, #5, #6 plus the enumeration/case mandates:
 - full cycle signup -> logout -> login works through TestClient;
 - login matches email case-insensitively;
 - wrong-password AND unknown-email login yield the SAME generic error at 200
   and log nobody in (no user enumeration, no mutation);
 - GET /settings as crew -> 403; unauthenticated GET / and GET /settings -> 303
   redirect to /login (never 401/403 for the unauthenticated case).
"""

from __future__ import annotations

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


def visible_text(html):
    t = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", t).strip().lower()


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


def signup(client, *, email, password="password123", timezone="America/New_York", company="Acme Co"):
    return _get_then_post(client, "/signup", email=email, password=password,
                          timezone=timezone, text=company)


def login(client, *, email, password="password123"):
    return _get_then_post(client, "/login", email=email, password=password)


def owner_csrf(client):
    r = client.get("/settings")
    return extract_csrf(r.text) if r.status_code == 200 else None


# --------------------------------------------------------------------------- #
# #2 -- full cycle signup -> logout -> login.
# --------------------------------------------------------------------------- #
def test_full_cycle_signup_logout_login(app):
    with TestClient(app) as c:
        resp = signup(c, email="cycle@example.com", password="password123",
                      company="Cycle Co")
        assert resp.status_code == 303
        assert location_path(resp) == "/"

        home = c.get("/")
        assert home.status_code == 200
        assert "Cycle Co" in home.text, "home should display the company name"

        token = owner_csrf(c)
        assert token
        out = c.post("/logout", data={"csrf_token": token}, follow_redirects=False)
        assert out.status_code == 303
        assert location_path(out) == "/login"

        # Session cleared -> unauthenticated home redirects.
        assert c.get("/", follow_redirects=False).status_code == 303

        back = login(c, email="cycle@example.com", password="password123")
        assert back.status_code == 303
        assert location_path(back) == "/"
        assert c.get("/", follow_redirects=False).status_code == 200


# --------------------------------------------------------------------------- #
# Login matches email case-insensitively.
# --------------------------------------------------------------------------- #
def test_login_email_is_case_insensitive(app):
    make_user(app, email="alice@example.com", password="password123",
              role="owner", company="Acme Co")
    with TestClient(app) as c:
        resp = login(c, email="ALICE@EXAMPLE.COM", password="password123")
        assert resp.status_code == 303, "login must match email case-insensitively"
        assert location_path(resp) == "/"
        assert c.get("/", follow_redirects=False).status_code == 200


# --------------------------------------------------------------------------- #
# #6 -- wrong password & unknown email: same generic error, 200, no login,
# no mutation, no enumeration.
# --------------------------------------------------------------------------- #
def test_wrong_password_and_unknown_email_are_indistinguishable(app):
    make_user(app, email="real@example.com", password="password123",
              role="owner", company="Acme Co")
    with TestClient(app) as c:
        wrong_pw = login(c, email="real@example.com", password="wrong-password")
        assert wrong_pw.status_code == 200
        assert c.get("/", follow_redirects=False).status_code == 303  # not logged in

        unknown = login(c, email="ghost@example.com", password="whatever123")
        assert unknown.status_code == 200
        assert c.get("/", follow_redirects=False).status_code == 303

        # Same generic, visible error for both -> no user enumeration.
        # (Comparing tag-stripped visible text: input values / csrf tokens are
        # attributes and drop out, so only human-visible copy is compared.)
        assert visible_text(wrong_pw.text) == visible_text(unknown.text)

    # No account was created or removed by the failed logins.
    with db_session(app) as db:
        assert db.query(User).count() == 1


def test_wrong_password_does_not_establish_a_session(app):
    make_user(app, email="real@example.com", password="password123",
              role="owner", company="Acme Co")
    with TestClient(app) as c:
        resp = login(c, email="real@example.com", password="nope-nope-nope")
        assert resp.status_code == 200
        # Definitely not authenticated.
        assert c.get("/", follow_redirects=False).status_code == 303


# --------------------------------------------------------------------------- #
# #5 -- role gating and unauthenticated redirects.
# --------------------------------------------------------------------------- #
def test_settings_forbidden_for_crew(app):
    make_user(app, email="crew@example.com", role="crew", company="Acme Co")
    with TestClient(app) as c:
        assert login(c, email="crew@example.com").status_code == 303  # login works
        resp = c.get("/settings", follow_redirects=False)
        assert resp.status_code == 403, "crew must be forbidden from owner-only settings"


def test_settings_allowed_for_owner(app):
    """Positive control: an owner may GET /settings (so the 403 above is role-based)."""
    make_user(app, email="owner@example.com", role="owner", company="Acme Co")
    with TestClient(app) as c:
        assert login(c, email="owner@example.com").status_code == 303
        resp = c.get("/settings", follow_redirects=False)
        assert resp.status_code == 200


def test_unauthenticated_home_redirects_303_to_login(app):
    with TestClient(app) as c:
        resp = c.get("/", follow_redirects=False)
        assert resp.status_code == 303
        assert location_path(resp) == "/login"


def test_unauthenticated_settings_redirects_303_to_login_not_403(app):
    with TestClient(app) as c:
        resp = c.get("/settings", follow_redirects=False)
        assert resp.status_code == 303, "unauthenticated must redirect, not 403"
        assert location_path(resp) == "/login"
