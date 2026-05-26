"""Integration smoke test — spawns a real fovux-mcp server and exercises endpoints.

This test requires the full fovux-mcp installation and is expected to run
only in CI with the `integration` marker.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

from tests.path_helpers import find_package_root

REPO_ROOT = find_package_root(Path(__file__))
SERVER_PORT = 17823  # Use a non-default port to avoid conflicts


@pytest.fixture(scope="module")
def fovux_server():
    """Start a fovux-mcp server for the duration of the module."""
    proc = subprocess.Popen(  # noqa: S603, S607
        [
            sys.executable,
            "-m",
            "fovux.cli",
            "serve",
            "--http",
            "--tcp",
            "--port",
            str(SERVER_PORT),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(REPO_ROOT),
    )

    # Wait for the server to start
    base_url = f"http://127.0.0.1:{SERVER_PORT}"
    for _ in range(30):
        try:
            resp = requests.get(f"{base_url}/health", timeout=1)
            if resp.ok:
                break
        except requests.ConnectionError:
            pass
        time.sleep(0.5)
    else:
        proc.kill()
        raise RuntimeError("fovux-mcp server did not start within 15 seconds")

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.mark.integration
class TestRealServerSmoke:
    """Smoke tests against a real fovux-mcp server."""

    def test_health_returns_version(self, fovux_server: str) -> None:
        resp = requests.get(f"{fovux_server}/health", timeout=10)
        assert resp.ok
        data = resp.json()
        assert "version" in data
        assert "service" in data
        assert data["service"] == "fovux-mcp"

    def test_health_version_matches_package(self, fovux_server: str) -> None:
        from fovux import __version__

        resp = requests.get(f"{fovux_server}/health", timeout=10)
        data = resp.json()
        assert data["version"] == __version__

    def test_list_runs_returns_list(self, fovux_server: str) -> None:
        resp = requests.get(f"{fovux_server}/runs", timeout=10)
        # May return 401 if auth is required — that's also acceptable
        assert resp.status_code in (200, 401)
        if resp.ok:
            assert isinstance(resp.json(), list)

    def test_unknown_tool_returns_404(self, fovux_server: str) -> None:
        resp = requests.post(
            f"{fovux_server}/tools/nonexistent_tool",
            json={},
            timeout=10,
        )
        assert resp.status_code in (404, 401)
