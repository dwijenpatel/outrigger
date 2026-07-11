"""Held-out adversarial tests: signup validation & persistence.

Attacks acceptance #1 and #6:
 - exactly ONE Company + ONE owner User created; password bcrypt-hashed
   ("$2..."), never stored/echoed as plaintext; email stored LOWERCASE;
 - short password (<8) and invalid IANA timezone rejected, NOTHING created;
 - duplicate email (globally, across a would-be new company; case-insensitive)
   re-renders with an error at 200 and creates NOTHING.

Signup is driven naming-agnostically: field names are discovered from the
rendered form and every non-special text field is filled with a valid value,
so these tests hold under any reasonable choice of form field names.
"""

from __future__ import annotations

import re
from contextlib import contextmanager

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


def signup(client, *, email, password="password123", timezone="America/New_York", company="Acme Co"):
    r = client.get("/signup")
    data = build_form(r.text, email=email, password=password, timezone=timezone, text=company)
    return client.post("/signup", data=data, follow_redirects=False)


# --------------------------------------------------------------------------- #
# #1 -- exactly one Company + one owner User; bcrypt hash; lowercase email.
# --------------------------------------------------------------------------- #
def test_signup_creates_exactly_one_company_and_one_owner(app):
    with TestClient(app) as c:
        resp = signup(c, email="Owner@Example.COM", password="password123",
                      company="Acme Co")
        assert resp.status_code == 303
        assert location_path(resp) == "/"

    from app.security import verify_password

    with db_session(app) as db:
        companies = db.query(Company).all()
        users = db.query(User).all()
        assert len(companies) == 1
        assert len(users) == 1

        user = users[0]
        assert user.role == "owner"
        assert user.company_id == companies[0].id
        # email stored lowercase
        assert user.email == "owner@example.com"
        # bcrypt hash present, plaintext never stored
        assert isinstance(user.password_hash, str)
        assert user.password_hash.startswith("$2")
        assert user.password_hash != "password123"
        assert "password123" not in user.password_hash
        assert verify_password("password123", user.password_hash) is True
        assert verify_password("wrong-password", user.password_hash) is False


def test_signup_password_never_appears_plaintext_in_any_column(app):
    secret = "correcthorse42"
    with TestClient(app) as c:
        resp = signup(c, email="row@example.com", password=secret, company="Acme Co")
        assert resp.status_code == 303

    with db_session(app) as db:
        user = db.query(User).one()
        for attr in ("email", "password_hash", "role", "name"):
            value = getattr(user, attr, None)
            assert value != secret
            assert not (isinstance(value, str) and secret in value)


# --------------------------------------------------------------------------- #
# #6 / validation -- short password & invalid timezone rejected, nothing made.
# --------------------------------------------------------------------------- #
def test_short_password_rejected_and_nothing_created(app):
    with TestClient(app) as c:
        resp = signup(c, email="shorty@example.com", password="seven77",  # 7 chars
                      company="Acme Co")
        assert resp.status_code == 200, "short password must re-render the form"

    with db_session(app) as db:
        assert db.query(User).count() == 0
        assert db.query(Company).count() == 0


def test_password_length_boundary_eight_is_accepted(app):
    with TestClient(app) as c:
        resp = signup(c, email="eight@example.com", password="abcdefgh",  # exactly 8
                      company="Acme Co")
        assert resp.status_code == 303, "min length is 8 -> 8 chars must be allowed"

    with db_session(app) as db:
        assert db.query(User).count() == 1


def test_invalid_timezone_rejected_and_nothing_created(app):
    with TestClient(app) as c:
        resp = signup(c, email="tz@example.com", timezone="Mars/Phobos",
                      company="Acme Co")
        assert resp.status_code == 200, "invalid IANA timezone must re-render the form"

    with db_session(app) as db:
        assert db.query(User).count() == 0
        assert db.query(Company).count() == 0


# --------------------------------------------------------------------------- #
# #6 -- duplicate email (globally, across a new company; case-insensitive)
# is rejected and creates nothing new.
# --------------------------------------------------------------------------- #
def test_duplicate_email_rejected_globally_nothing_created(app):
    with TestClient(app) as c1:
        assert signup(c1, email="dup@example.com", company="First Co").status_code == 303

    with TestClient(app) as c2:
        # Different (would-be new) company, SAME email -> global uniqueness blocks it.
        resp = signup(c2, email="dup@example.com", company="Second Co")
        assert resp.status_code == 200, "duplicate email must re-render, not redirect"

    with db_session(app) as db:
        assert db.query(User).count() == 1, "second user must NOT be created"
        assert db.query(Company).count() == 1, "second company must NOT be created"


def test_duplicate_email_detection_is_case_insensitive(app):
    with TestClient(app) as c1:
        assert signup(c1, email="dup@example.com", company="First Co").status_code == 303

    with TestClient(app) as c2:
        resp = signup(c2, email="DUP@Example.COM", company="Second Co")
        assert resp.status_code == 200

    with db_session(app) as db:
        assert db.query(User).count() == 1
