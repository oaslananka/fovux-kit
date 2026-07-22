"""Contract tests for the HTTP bridge consumed by Fovux Studio."""

from __future__ import annotations

import pytest
from starlette import testclient as starlette_testclient

from fovux.http.app import create_app

TestClient = starlette_testclient.TestClient


def test_starlette_testclient_uses_httpx2_backend() -> None:
    """Starlette should use its supported httpx2 test backend without fallback warnings."""
    assert starlette_testclient.httpx.__name__ == "httpx2"


@pytest.mark.contract
def test_openapi_exposes_studio_http_contract() -> None:
    """OpenAPI should keep the Studio-facing route surface stable."""
    with TestClient(create_app()) as client:
        client.app.state.nonlocal_bind_allowed = True
        headers = {"Authorization": f"Bearer {client.app.state.auth_token}"}
        schema = client.get("/openapi.json", headers=headers).json()

    paths = schema["paths"]
    assert "/runs" in paths
    assert "/runs/{run_id}" in paths
    assert "/runs/{run_id}/metrics" in paths
    assert "/tools/{name}" in paths
    assert paths["/tools/{name}"]["post"]["parameters"][0]["name"] == "name"
