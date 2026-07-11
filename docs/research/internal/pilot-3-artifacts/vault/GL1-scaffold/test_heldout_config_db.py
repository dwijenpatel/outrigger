"""Held-out tests: config env defaults, per-app engine, get_db lifecycle,
models.Base (GL1-scaffold spec).

Spec pins:
- app/config.py reads GREENLANE_DB (default sqlite:///greenlane.db) and
  GREENLANE_SECRET (default "dev-secret-change-me") from env.
- Two create_app() calls with different GREENLANE_DB values do not share
  state (engine per-app, not module-global-mutated).
- app/db.py exposes a get_db FastAPI dependency yielding a session and
  closing it after the request.
- app/models.py: SQLAlchemy Base (DeclarativeBase), no domain tables yet.
"""

import importlib
import inspect
import os

import pytest
from sqlalchemy.orm import DeclarativeBase, Session

# ---------------------------------------------------------------------------
# config defaults / env reading
# ---------------------------------------------------------------------------


def _harvest_strings(obj, out, depth=0):
    if depth > 3:
        return
    if isinstance(obj, str):
        out.add(obj)
        return
    if isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            _harvest_strings(v, out, depth + 1)
        return
    if isinstance(obj, dict):
        for v in obj.values():
            _harvest_strings(v, out, depth + 1)
        return
    d = getattr(obj, "__dict__", None)
    if isinstance(d, dict):
        for v in d.values():
            _harvest_strings(v, out, depth + 1)


def _config_strings(cfg_module):
    """Collect every string reachable from app.config's public surface,
    including values held by settings objects/classes/factories."""
    out: set = set()
    for name, value in vars(cfg_module).items():
        if name.startswith("__"):
            continue
        if inspect.ismodule(value):
            continue
        _harvest_strings(value, out)
        lowered = name.lower()
        if "settings" in lowered or "config" in lowered:
            if inspect.isclass(value):
                try:
                    _harvest_strings(value(), out)
                except Exception:
                    pass
            elif callable(value):
                try:
                    _harvest_strings(value(), out)
                except Exception:
                    pass
    return out


def _reload_config_with_env(env_updates, env_removals):
    saved = {}
    for key in set(env_removals) | set(env_updates):
        saved[key] = os.environ.pop(key, None)
    for key, val in env_updates.items():
        os.environ[key] = val
    import app.config as cfg

    try:
        cfg = importlib.reload(cfg)
        return _config_strings(cfg)
    finally:
        for key, val in saved.items():
            if val is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = val
        importlib.reload(cfg)


def test_config_defaults_with_env_unset():
    strings = _reload_config_with_env(
        {}, ["GREENLANE_DB", "GREENLANE_SECRET"]
    )
    assert "sqlite:///greenlane.db" in strings, (
        "GREENLANE_DB default must be sqlite:///greenlane.db "
        f"(saw strings: {sorted(strings)[:20]})"
    )
    assert "dev-secret-change-me" in strings, (
        "GREENLANE_SECRET default must be 'dev-secret-change-me'"
    )


def test_config_reads_db_url_from_env():
    sentinel = "sqlite:///heldout-sentinel-db-url.db"
    strings = _reload_config_with_env(
        {"GREENLANE_DB": sentinel}, ["GREENLANE_SECRET"]
    )
    assert sentinel in strings


def test_config_reads_secret_from_env():
    sentinel = "heldout-sentinel-secret"
    strings = _reload_config_with_env(
        {"GREENLANE_SECRET": sentinel}, ["GREENLANE_DB"]
    )
    assert sentinel in strings


# ---------------------------------------------------------------------------
# acceptance criterion 3: per-app engine
# ---------------------------------------------------------------------------


def test_two_apps_with_different_dbs_do_not_share_state(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app import create_app

    file_a = tmp_path / "a.db"
    file_b = tmp_path / "b.db"

    monkeypatch.setenv("GREENLANE_DB", f"sqlite:///{file_a}")
    app_a = create_app()
    monkeypatch.setenv("GREENLANE_DB", f"sqlite:///{file_b}")
    app_b = create_app()

    # Start app_a AFTER app_b was created: if the engine were a mutated
    # module global, app_a's create_all would hit b.db and a.db would
    # never come into existence.
    with TestClient(app_a) as ca:
        assert ca.get("/health").status_code == 200
        assert file_a.exists(), (
            "app_a's startup create_all did not touch the GREENLANE_DB it "
            "was created with -- engine state is shared between apps"
        )

    with TestClient(app_b) as cb:
        assert cb.get("/health").status_code == 200
        assert file_b.exists(), (
            "app_b's startup create_all did not touch the GREENLANE_DB it "
            "was created with"
        )


# ---------------------------------------------------------------------------
# get_db dependency lifecycle
# ---------------------------------------------------------------------------


def _spy_close(session):
    calls = []
    orig = session.close

    def spy(*a, **k):
        calls.append(True)
        return orig(*a, **k)

    session.close = spy  # type: ignore[method-assign]
    return calls


def _drive_get_db(action):
    """Run get_db through the generator-dependency protocol.

    Returns (yielded_session, close_calls).
    """
    from app.db import get_db

    if inspect.isasyncgenfunction(get_db):
        import asyncio

        async def run():
            gen = get_db()
            session = await gen.__anext__()
            calls = _spy_close(session)
            if action == "finish":
                try:
                    await gen.__anext__()
                except StopAsyncIteration:
                    pass
            else:
                try:
                    await gen.athrow(RuntimeError("heldout boom"))
                except (RuntimeError, StopAsyncIteration):
                    pass
            return session, calls

        return asyncio.run(run())

    assert inspect.isgeneratorfunction(get_db), (
        "get_db must be a (sync or async) generator dependency that yields "
        "a session"
    )
    gen = get_db()
    session = next(gen)
    calls = _spy_close(session)
    if action == "finish":
        try:
            next(gen)
        except StopIteration:
            pass
    else:
        try:
            gen.throw(RuntimeError("heldout boom"))
        except (RuntimeError, StopIteration):
            pass
    return session, calls


def test_get_db_yields_a_sqlalchemy_session():
    session, _ = _drive_get_db("finish")
    assert isinstance(session, Session)


def test_get_db_closes_session_after_request():
    _, close_calls = _drive_get_db("finish")
    assert close_calls, "get_db must close the session after the request"


def test_get_db_closes_session_even_on_request_error():
    _, close_calls = _drive_get_db("throw")
    assert close_calls, (
        "get_db must close the session even when the request errors "
        "(yield inside try/finally)"
    )


# ---------------------------------------------------------------------------
# models.Base
# ---------------------------------------------------------------------------


def test_models_base_is_declarative_base():
    from app.models import Base

    assert isinstance(Base, type)
    assert issubclass(Base, DeclarativeBase)


def test_models_has_no_domain_tables_yet():
    from app.models import Base

    assert len(Base.metadata.tables) == 0, (
        "GL1 pins 'Base only for now' -- no domain tables in this task, "
        f"found: {sorted(Base.metadata.tables)}"
    )
