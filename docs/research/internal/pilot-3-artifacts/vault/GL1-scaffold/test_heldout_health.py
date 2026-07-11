"""Held-out tests: GET /health contract (GL1-scaffold spec).

Spec pins: `GET /health` -> JSON `{"status": "ok"}`, HTTP 200.
"""


def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200


def test_health_body_is_exactly_status_ok(client):
    r = client.get("/health")
    # Exact body pinned by the spec: no extra keys, exact value.
    assert r.json() == {"status": "ok"}


def test_health_is_json_content_type(client):
    r = client.get("/health")
    ctype = r.headers.get("content-type", "")
    assert ctype.split(";")[0].strip() == "application/json"


def test_health_on_a_fresh_factory_app(tmp_path, monkeypatch):
    """The route must come from create_app() itself, not from test fixtures."""
    monkeypatch.setenv("GREENLANE_DB", f"sqlite:///{tmp_path / 'health.db'}")
    from fastapi.testclient import TestClient

    from app import create_app

    application = create_app()
    with TestClient(application) as c:
        r = c.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
