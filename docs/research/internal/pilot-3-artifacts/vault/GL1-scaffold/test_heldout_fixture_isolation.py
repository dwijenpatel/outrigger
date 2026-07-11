"""Held-out tests: conftest fixture contract (GL1-scaffold spec).

Spec pins:
- fixture `app`: fresh app wired to a brand-new in-memory SQLite DB per
  test (sqlite:// StaticPool engine injected before create_all).
- fixture `client`: TestClient over that app.
"""

from pathlib import Path

import app as app_pkg
from fastapi import Depends
from sqlalchemy import text

PROJECT_ROOT = Path(app_pkg.__file__).resolve().parent.parent

_TABLE = "heldout_iso_probe"


def _install_counter_route(app):
    """Route that writes/reads through the app's canonical DB dependency."""
    from app.db import get_db

    @app.get("/__heldout_counter")
    def counter(session=Depends(get_db)):
        session.execute(
            text(f"CREATE TABLE IF NOT EXISTS {_TABLE} (x INTEGER)")
        )
        session.execute(text(f"INSERT INTO {_TABLE} (x) VALUES (1)"))
        session.commit()
        n = session.execute(text(f"SELECT COUNT(*) FROM {_TABLE}")).scalar()
        return {"count": n}


def test_client_is_bound_to_the_app_fixture(app, client):
    @app.get("/__heldout_binding_probe")
    def probe():
        return {"probe": "bound"}

    r = client.get("/__heldout_binding_probe")
    assert r.status_code == 200
    assert r.json() == {"probe": "bound"}


def test_db_is_shared_across_requests_within_one_test(app, client):
    """sqlite:// + StaticPool means every request in a test sees the SAME
    in-memory DB: a second request must observe the first one's row."""
    _install_counter_route(app)
    assert client.get("/__heldout_counter").json()["count"] == 1
    assert client.get("/__heldout_counter").json()["count"] == 2


def test_db_is_brand_new_per_test_part1(app, client):
    _install_counter_route(app)
    assert client.get("/__heldout_counter").json()["count"] == 1, (
        "each test must start with a brand-new in-memory DB"
    )


def test_db_is_brand_new_per_test_part2(app, client):
    # If the DB (or a file-backed DB) leaked from the previous test, the
    # probe table would already contain rows and count would exceed 1.
    _install_counter_route(app)
    assert client.get("/__heldout_counter").json()["count"] == 1, (
        "in-memory DB state leaked between tests -- fixture is not "
        "brand-new per test"
    )


def test_fixture_tests_do_not_create_dbfile_on_disk(app, client):
    """The fixtures pin an in-memory DB; exercising the app must not
    materialize the default sqlite:///greenlane.db file."""
    dbfile = PROJECT_ROOT / "greenlane.db"
    existed_before = dbfile.exists()

    _install_counter_route(app)
    assert client.get("/health").status_code == 200
    client.get("/__heldout_counter")

    if not existed_before:
        assert not dbfile.exists(), (
            "running against the test fixtures created greenlane.db on "
            "disk -- the fixture app is not wired to the in-memory DB"
        )
