"""Held-out adversarial tests: tenant scoping helpers + session payload.

The CRITICAL invariant (acceptance #3): a cross-company object id resolves to
404 -- uniform with a nonexistent id, and NEVER 403 or a redirect. This task
ships no route that takes an object id (customer/schedule models come later),
so the invariant is pinned directly on the helpers ``get_or_404`` /
``company_query`` that every later route depends on.

These tests import nothing implementation-specific beyond the spec's declared
public surface (``app.models.Company/User``, ``app.security`` helpers).
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

from starlette.exceptions import HTTPException as _StarletteHTTPException

try:  # fastapi.HTTPException subclasses starlette's, but catch both explicitly
    from fastapi import HTTPException as _FastAPIHTTPException

    HTTP_EXC = (_StarletteHTTPException, _FastAPIHTTPException)
except Exception:  # pragma: no cover
    HTTP_EXC = (_StarletteHTTPException,)


# --------------------------------------------------------------------------- #
# Shared, self-contained helpers (held-out files cannot import a sibling
# module -- only test_heldout_*.py are harvested -- so each file is standalone).
# --------------------------------------------------------------------------- #
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


def decode_session(cookie_value):
    if not cookie_value:
        return None
    for part in cookie_value.split("."):
        p = part.strip().rstrip("=")
        p = p + "=" * (-len(p) % 4)
        for dec in (base64.b64decode, base64.urlsafe_b64decode):
            try:
                obj = json.loads(dec(p))
                if isinstance(obj, dict):
                    return obj
            except Exception:
                continue
    return None


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


# --------------------------------------------------------------------------- #
# CRITICAL: cross-tenant reads resolve to 404, uniform with nonexistent.
# --------------------------------------------------------------------------- #
def test_get_or_404_cross_company_is_404_not_403_not_redirect(client, app):
    from app.security import get_or_404

    _a_company, a_user = make_user(app, email="a@example.com", company="Company A")
    _b_company, b_user = make_user(app, email="b@example.com", company="Company B")

    with db_session(app) as db:
        user_a = db.query(User).filter_by(id=a_user).one()

        # Cross-company object owned by B, requested through A's scope -> 404.
        with pytest.raises(HTTP_EXC) as excinfo:
            get_or_404(db, User, b_user, user_a)
        assert excinfo.value.status_code == 404

        # A genuinely nonexistent id -> ALSO 404 (uniform; no enumeration).
        with pytest.raises(HTTP_EXC) as excinfo_missing:
            get_or_404(db, User, 10_000_000, user_a)
        assert excinfo_missing.value.status_code == 404

        # Same status for cross-company and nonexistent (indistinguishable).
        assert excinfo.value.status_code == excinfo_missing.value.status_code


def test_get_or_404_returns_own_company_object(client, app):
    from app.security import get_or_404

    _a_company, a_user = make_user(app, email="a@example.com", company="Company A")

    with db_session(app) as db:
        user_a = db.query(User).filter_by(id=a_user).one()
        got = get_or_404(db, User, a_user, user_a)
        assert got is not None
        assert got.id == a_user
        assert got.company_id == user_a.company_id


def test_get_or_404_ignores_a_company_id_kwarg_if_accepted(client, app):
    """company_id must NEVER come from the caller -- only user.company_id.

    If ``get_or_404`` happens to accept a ``company_id`` keyword, supplying
    company B's id must NOT unlock B's object for user A. If it does not accept
    such a kwarg, the helper is trivially safe and this test is a no-op pass.
    """
    from app.security import get_or_404

    _a_company, a_user = make_user(app, email="a@example.com", company="Company A")
    b_company, b_user = make_user(app, email="b@example.com", company="Company B")

    with db_session(app) as db:
        user_a = db.query(User).filter_by(id=a_user).one()
        try:
            result = get_or_404(db, User, b_user, user_a, company_id=b_company)
        except TypeError:
            pytest.skip("get_or_404 does not accept a company_id override -- safe by construction")
        except HTTP_EXC as exc:
            assert exc.status_code == 404
            return
        # If it returned something, it must NOT be B's cross-tenant object.
        assert result is None or getattr(result, "company_id", None) == user_a.company_id


# --------------------------------------------------------------------------- #
# company_query is scoped to the session user's company.
# --------------------------------------------------------------------------- #
def test_company_query_only_returns_own_company_rows(client, app):
    from app.security import company_query

    _a_company, a_user = make_user(app, email="a@example.com", company="Company A")
    _b_company, b_user = make_user(app, email="b@example.com", company="Company B")

    with db_session(app) as db:
        user_a = db.query(User).filter_by(id=a_user).one()
        q = company_query(db, User, user_a)
        try:
            rows = q.all()  # legacy Query
        except AttributeError:
            rows = db.execute(q).scalars().all()  # 2.0 Select
        ids = {r.id for r in rows}
        assert a_user in ids, "own-company row must be visible"
        assert b_user not in ids, "another company's row leaked through company_query"
        assert all(r.company_id == user_a.company_id for r in rows)


# --------------------------------------------------------------------------- #
# Session payload must not smuggle role / company (only user_id identifies).
# --------------------------------------------------------------------------- #
def test_session_payload_carries_no_role_or_company(client, app):
    _cid, uid = make_user(app, email="owner@example.com", role="owner", company="Acme Co")

    with TestClient(app) as c:
        resp = login(c, email="owner@example.com")
        assert resp.status_code == 303  # login succeeded, session set

        payload = decode_session(c.cookies.get("gl_session"))
        assert payload is not None, "gl_session cookie missing or not decodable"
        assert payload.get("user_id") == uid
        for forbidden in ("role", "company_id", "company", "email", "is_owner", "owner"):
            assert forbidden not in payload, f"session smuggled {forbidden!r}"
