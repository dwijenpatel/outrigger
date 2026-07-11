"""Held-out tests: run.py uvicorn entrypoint (GL1-scaffold spec).

Spec pins (acceptance criterion 4): run.py starts uvicorn on port 8000
when executed directly.
"""

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

import app as app_pkg

PROJECT_ROOT = Path(app_pkg.__file__).resolve().parent.parent

PORT = 8000


def _port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", PORT)) == 0


def test_runpy_mentions_uvicorn():
    src = (PROJECT_ROOT / "run.py").read_text()
    assert "uvicorn" in src, "run.py must be a uvicorn entrypoint"


def test_runpy_serves_health_on_port_8000(tmp_path):
    if _port_in_use():
        pytest.skip("port 8000 already in use on this machine")

    env = dict(os.environ)
    # Point the app at a scratch DB so executing run.py can never dirty
    # the repo tree with a stray greenlane.db (git status is gate input).
    env["GREENLANE_DB"] = f"sqlite:///{tmp_path / 'run.db'}"

    proc = subprocess.Popen(
        [sys.executable, str(PROJECT_ROOT / "run.py")],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        deadline = time.monotonic() + 25
        last_err = None
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                pytest.fail(
                    f"run.py exited early with code {proc.returncode} "
                    "instead of serving on port 8000"
                )
            try:
                r = httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=1.0)
                assert r.status_code == 200
                assert r.json() == {"status": "ok"}
                break
            except (httpx.TransportError, AssertionError) as exc:
                last_err = exc
                time.sleep(0.25)
        else:
            pytest.fail(
                f"run.py never answered on port {PORT} within 25s "
                f"(last error: {last_err!r})"
            )
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=10)
