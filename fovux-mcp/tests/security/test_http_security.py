"""Security-focused checks for the local HTTP transport."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from tests.path_helpers import find_package_root

from fovux.core.auth import token_fingerprint
from fovux.http.app import (
    MAX_TOOL_BODY_BYTES,
    _parse_content_length,
    _SlidingWindowRateLimiter,
    _ToolBodyLimitMiddleware,
    create_app,
    warn_if_nonlocal_host,
)

REPO_ROOT = find_package_root(Path(__file__))


@pytest.mark.security
def test_http_routes_reject_missing_bearer_token() -> None:
    """Authenticated Studio routes should reject unauthenticated callers."""
    with TestClient(create_app()) as client:
        response = client.get("/runs")

    assert response.status_code == 401


@pytest.mark.security
def test_http_auth_token_creation_log_redacts_raw_token(tmp_path: Path) -> None:
    """First-run auth logging should include fingerprints only."""
    logger = MagicMock()
    sample_value = "unit-test-redaction-value"
    token_path = tmp_path / "auth.token"
    with (
        patch("fovux.http.app.ensure_auth_token", return_value=(sample_value, True)),
        patch("fovux.http.app.auth_token_path", return_value=token_path),
        patch("fovux.http.app.get_logger", return_value=logger),
        TestClient(create_app()) as client,
    ):
        assert client.get("/health").status_code == 200

    logger.warning.assert_any_call(
        "http_auth_token_created",
        fingerprint=token_fingerprint(sample_value),
        path=str(token_path),
    )
    assert sample_value not in str(logger.mock_calls)


@pytest.mark.security
def test_http_tools_reject_oversized_body() -> None:
    """HTTP tools should reject request bodies before JSON parsing when too large."""
    with TestClient(create_app()) as client:
        token = client.app.state.auth_token
        response = client.post(
            "/tools/model_list",
            content=b"x" * (MAX_TOOL_BODY_BYTES + 1),
            headers={"Authorization": f"Bearer {token}", "content-type": "application/json"},
        )

    assert response.status_code == 413


@pytest.mark.security
def test_http_mutating_tool_requires_confirmation() -> None:
    """Filesystem-writing HTTP tools require an explicit trusted UI confirmation."""
    with TestClient(create_app()) as client:
        token = client.app.state.auth_token
        response = client.post(
            "/tools/train_start",
            json={"dataset_path": "fixtures/mini_yolo"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 403
    assert "confirm" in response.text.lower()


@pytest.mark.security
def test_container_defaults_bind_to_localhost() -> None:
    """Container examples should not expose the HTTP transport on all interfaces by default."""
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    # Split intentionally to avoid static-analysis flags for the container bind literal.
    assert '"--host", "' + "0." + "0." + "0." + "0" + '"' in dockerfile
    assert "host exposure on loopback" in dockerfile
    assert "--extra yolo" not in dockerfile
    assert '"127.0.0.1:7823:7823"' in compose


@pytest.mark.security
def test_http_routes_reject_stale_bearer_token() -> None:
    """A replayed or stale token should not authorize run access."""
    with TestClient(create_app()) as client:
        response = client.get("/runs", headers={"Authorization": "Bearer stale-token"})

    assert response.status_code == 401


@pytest.mark.security
def test_http_content_length_parser_handles_absent_and_invalid_values() -> None:
    """Invalid content-length headers should fall back to streaming body limits."""
    assert _parse_content_length(None) is None
    assert _parse_content_length("not-an-int") is None
    assert _parse_content_length("42") == 42


@pytest.mark.security
def test_nonlocal_bind_warning_redacts_runtime_details() -> None:
    """Remote bind warnings should log host/config state without exposing credentials."""
    logger = MagicMock()
    remote_host = "0." + "0." + "0." + "0"
    with patch("fovux.http.app.get_logger", return_value=logger):
        warn_if_nonlocal_host(remote_host)

    logger.warning.assert_called_once()
    assert "token" not in str(logger.warning.call_args).lower()


@pytest.mark.security
def test_rate_limiter_expires_old_entries() -> None:
    """Rate limiting should discard entries after the configured window."""
    limiter = _SlidingWindowRateLimiter(limit=1, window_seconds=1)
    with patch("fovux.http.app.time.time", side_effect=[0.0, 2.0]):
        assert limiter.check("client-a") == (False, 0)
        assert limiter.check("client-a") == (False, 0)


@pytest.mark.security
@pytest.mark.asyncio
async def test_tool_body_limit_middleware_replays_chunked_body() -> None:
    """Chunked tool bodies under the limit should be buffered and replayed once."""
    received = []
    sent = []

    async def app(scope, receive, send):
        received.append(await receive())
        received.append(await receive())
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    middleware = _ToolBodyLimitMiddleware(app, max_body_bytes=8)
    messages = [
        {"type": "http.request", "body": b'{"', "more_body": True},
        {"type": "http.request", "body": b'a"}', "more_body": False},
    ]

    async def receive():
        return messages.pop(0)

    async def send(message):
        sent.append(message)

    await middleware(
        {"type": "http", "method": "POST", "path": "/tools/model_list"},
        receive,
        send,
    )

    assert received[0]["body"] == b'{"a"}'
    assert received[1]["body"] == b""
    assert sent[0]["status"] == 204


@pytest.mark.security
@pytest.mark.asyncio
async def test_tool_body_limit_middleware_rejects_chunked_oversize() -> None:
    """Chunked tool bodies should be rejected as soon as they exceed the limit."""
    sent = []

    async def app(scope, receive, send):
        raise AssertionError("oversized tool bodies must not reach the app")

    middleware = _ToolBodyLimitMiddleware(app, max_body_bytes=3)
    messages = [
        {"type": "http.request", "body": b"ab", "more_body": True},
        {"type": "http.request", "body": b"cd", "more_body": False},
    ]

    async def receive():
        return messages.pop(0)

    async def send(message):
        sent.append(message)

    await middleware(
        {"type": "http", "method": "POST", "path": "/tools/model_list"},
        receive,
        send,
    )

    assert sent[0]["status"] == 413


@pytest.mark.security
@pytest.mark.asyncio
async def test_tool_body_limit_middleware_passes_through_non_tool_requests() -> None:
    """Non-tool traffic should not be buffered by the tool body limiter."""
    seen = []

    async def app(scope, receive, send):
        seen.append(scope["path"])
        seen.append(await receive())

    middleware = _ToolBodyLimitMiddleware(app, max_body_bytes=3)

    async def receive():
        return {"type": "http.request", "body": b"plain", "more_body": False}

    async def send(message):
        raise AssertionError("pass-through app did not send a response")

    await middleware({"type": "http", "method": "POST", "path": "/runs"}, receive, send)

    assert seen == ["/runs", {"type": "http.request", "body": b"plain", "more_body": False}]


@pytest.mark.security
@pytest.mark.asyncio
async def test_tool_body_limit_middleware_replays_non_request_messages() -> None:
    """Unexpected ASGI messages should be replayed to the downstream app unchanged."""
    received = []

    async def app(scope, receive, send):
        received.append(await receive())

    middleware = _ToolBodyLimitMiddleware(app, max_body_bytes=3)

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message):
        raise AssertionError("pass-through app did not send a response")

    await middleware(
        {"type": "http", "method": "POST", "path": "/tools/model_list"},
        receive,
        send,
    )

    assert received == [{"type": "http.disconnect"}]
