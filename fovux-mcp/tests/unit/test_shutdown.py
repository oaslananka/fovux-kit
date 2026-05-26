"""Tests for HTTP application shutdown behavior."""

from __future__ import annotations

from fastapi.testclient import TestClient

from fovux.http.app import create_app


def test_http_app_sets_shutdown_event_on_teardown() -> None:
    """Application lifespan should mark the shutdown event when the app stops."""
    app = create_app()
    with TestClient(app) as client:
        assert app.state.shutdown_event.is_set() is False
        response = client.get("/health")
        assert response.status_code == 200

    assert app.state.shutdown_event.is_set() is True
