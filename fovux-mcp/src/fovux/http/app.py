"""FastAPI application for the Fovux Studio local API.

Provides custom REST/SSE endpoints for fovux-studio to query run state, invoke
guarded tools, and stream live metrics. This is not an MCP Streamable HTTP
endpoint. Binds to 127.0.0.1 by default.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Send
from starlette.types import Scope as ASGIScope

from fovux import __version__
from fovux.core.auth import (
    ALL_SCOPES,
    Scope,
    auth_token_path,
    ensure_auth_token,
    is_known_session_token,
    resolve_session_scopes,
    token_fingerprint,
)
from fovux.core.errors import FovuxError
from fovux.core.logging import get_logger
from fovux.http.tool_proxy import (
    HttpScopeError,
    HttpToolPolicyError,
    check_scope,
    policy_for_tool,
)

_thread_local = threading.local()


class ThreadLocalStream:
    """Stream wrapper that redirects output based on thread-local context."""

    def __init__(self, original_stream: Any) -> None:  # noqa: ANN401
        """Initialize the thread local stream wrapper."""
        self.original_stream = original_stream

    def write(self, data: str) -> int:
        """Write data to the active thread local stream or default stream."""
        stream = getattr(_thread_local, "stream", None)
        if stream is not None:
            return stream.write(data)  # type: ignore[no-any-return]
        return self.original_stream.write(data)  # type: ignore[no-any-return]

    def flush(self) -> None:
        """Flush the active thread local stream or default stream."""
        stream = getattr(_thread_local, "stream", None)
        if stream is not None:
            stream.flush()
        else:
            self.original_stream.flush()

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Delegate missing attributes to the original stream."""
        return getattr(self.original_stream, name)


if not isinstance(sys.stdout, ThreadLocalStream):
    sys.stdout = ThreadLocalStream(sys.stdout)
if not isinstance(sys.stderr, ThreadLocalStream):
    sys.stderr = ThreadLocalStream(sys.stderr)


_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_ALLOWED_ORIGIN_HOST_SUFFIX = ".vscode-cdn.net"
_ALLOWED_ORIGIN_SCHEMES = {"https", "vscode-webview"}
DEFAULT_TOOL_RATE_LIMIT = 100
TOOL_RATE_LIMITS = {"train_start": 5}
MAX_TOOL_BODY_BYTES = 1024 * 1024
_NON_LOCAL_BIND_ALLOWED: bool = False


def set_nonlocal_bind_allowed(value: bool) -> None:
    """Set whether non-local IP addresses are allowed to bind."""
    global _NON_LOCAL_BIND_ALLOWED
    _NON_LOCAL_BIND_ALLOWED = value


def is_local_bind_host(host: str) -> bool:
    """Return whether a bind host is local-only."""
    normalized = host.strip().lower().strip("[]")
    return normalized in _LOCAL_HOSTS


def _is_allowed_origin(origin: str | None) -> bool:
    """Return whether a browser Origin is trusted for the Studio local API."""
    if not origin:
        return True
    parsed = urlsplit(origin)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme == "vscode-webview":
        return True
    if scheme in {"http", "https"} and host in _LOCAL_HOSTS:
        return True
    return scheme == "https" and (
        host == "vscode-cdn.net" or host.endswith(_ALLOWED_ORIGIN_HOST_SUFFIX)
    )


def _reject_invalid_origin(origin: str) -> JSONResponse:
    """Build a DNS-rebinding-safe invalid-Origin response."""
    return JSONResponse(
        status_code=403,
        content={
            "detail": "Origin is not allowed for the Fovux Studio local API.",
        },
    )


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger = get_logger(__name__)
    app.state.shutdown_event = asyncio.Event()
    token, created = ensure_auth_token()
    app.state.auth_token = token
    app.state.rate_limiter = _SlidingWindowRateLimiter(
        limit=DEFAULT_TOOL_RATE_LIMIT,
        window_seconds=60,
    )
    logger.info("http_app_start")
    if created:
        logger.warning(
            "http_auth_token_created",
            fingerprint=token_fingerprint(token),
            path=str(auth_token_path()),
        )
    else:
        logger.info(
            "http_auth_token_loaded",
            fingerprint=token_fingerprint(token),
            path=str(auth_token_path()),
        )
    try:
        yield
    finally:
        app.state.shutdown_event.set()
        logger.info("http_app_stop")


def create_app(*, enable_metrics: bool = False) -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI app instance.
    """
    app = FastAPI(
        title="Fovux Studio Local API",
        version=__version__,
        description="Local custom REST/SSE interface for the Fovux Studio VS Code extension.",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^(vscode-webview://.*|https://.*\.vscode-cdn\.net|https://vscode-cdn\.net|https?://(localhost|127\.0\.0\.1|\[::1\])(:[0-9]+)?)$",
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )
    app.add_middleware(_ToolBodyLimitMiddleware, max_body_bytes=MAX_TOOL_BODY_BYTES)
    app.state.metrics_enabled = enable_metrics
    app.state.tool_body_max_bytes = MAX_TOOL_BODY_BYTES
    from fovux.http.tool_proxy import HTTP_TOOL_POLICIES

    app.state.challenges = {}

    app.state.tool_semaphores = {
        name: asyncio.Semaphore(policy.concurrency_limit)
        for name, policy in HTTP_TOOL_POLICIES.items()
        if policy.enabled
    }
    app.state.tool_operations = {}
    app.state.tool_operation_results = {}
    app.state.active_operation_tasks = {}
    app.state.sse_listeners = []

    @app.middleware("http")
    async def _auth_and_rate_limit(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        origin = request.headers.get("Origin")
        if not _is_allowed_origin(origin):
            return _reject_invalid_origin(origin or "")

        if (
            request.method.upper() == "OPTIONS"
            and origin
            and request.headers.get("Access-Control-Request-Method")
        ):
            return await call_next(request)

        if request.url.path != "/health":
            auth_header = request.headers.get("Authorization", "")
            raw_token = auth_header.removeprefix("Bearer ").strip()
            full_token = request.app.state.auth_token

            scopes: set[Scope] = ALL_SCOPES
            if raw_token == full_token:
                scopes = ALL_SCOPES
            elif is_known_session_token(raw_token):
                scopes = resolve_session_scopes(raw_token)
            else:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing or invalid bearer token."},
                )

            client_ip = request.client.host if request.client is not None else "unknown"
            if not request.app.state.nonlocal_bind_allowed:
                if client_ip not in _LOCAL_HOSTS:
                    return JSONResponse(
                        status_code=403,
                        content={
                            "detail": "Non-local requests are not allowed. "
                            "Restart with --allow-nonlocal-bind to accept external connections."
                        },
                    )

            if request.method.upper() == "POST" and request.url.path.startswith("/tools/"):
                content_length = _parse_content_length(request.headers.get("content-length"))
                if content_length is not None and content_length > MAX_TOOL_BODY_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Tool request body is too large."},
                    )
                path_rest = request.url.path.removeprefix("/tools/")
                tool_name = path_rest.split("/", maxsplit=1)[0]
                is_challenge = path_rest.endswith("/challenge")

                if not is_challenge:
                    try:
                        policy = policy_for_tool(tool_name)
                        check_scope(policy, scopes)
                    except HttpToolPolicyError as exc:
                        return JSONResponse(
                            status_code=403,
                            content={
                                "detail": {
                                    "code": exc.code,
                                    "message": exc.message,
                                    "hint": exc.hint,
                                }
                            },
                        )
                    except HttpScopeError as exc:
                        return JSONResponse(
                            status_code=403,
                            content={
                                "detail": {
                                    "code": exc.code,
                                    "message": exc.message,
                                    "hint": exc.hint,
                                }
                            },
                        )
                    except FovuxError as exc:
                        return JSONResponse(
                            status_code=403,
                            content={
                                "detail": {
                                    "code": exc.code,
                                    "message": exc.message,
                                    "hint": exc.hint,
                                }
                            },
                        )

                limit = (
                    DEFAULT_TOOL_RATE_LIMIT
                    if is_challenge
                    else TOOL_RATE_LIMITS.get(tool_name, DEFAULT_TOOL_RATE_LIMIT)
                )
                bucket_key = f"{client_ip}:{'challenge' if is_challenge else 'tool'}:{tool_name}"
                limited, retry_after = request.app.state.rate_limiter.check(
                    bucket_key,
                    limit=limit,
                )
                if limited:
                    return JSONResponse(
                        status_code=429,
                        headers={"Retry-After": str(retry_after)},
                        content={"detail": "Tool request rate limit exceeded."},
                    )

        return await call_next(request)

    from fovux.http.routes import router

    app.include_router(router)
    app.state.nonlocal_bind_allowed = _NON_LOCAL_BIND_ALLOWED
    return app


def warn_if_nonlocal_host(host: str) -> None:
    """Log a warning when the Studio local API is configured for a non-local bind host."""
    if is_local_bind_host(host):
        return
    get_logger(__name__).warning(
        "studio_api_nonlocal_bind",
        host=host,
        message=(
            "The Fovux Studio local API is local-first. Non-local binding requires "
            "--allow-nonlocal-bind and must be protected by a private reverse proxy, "
            "network ACLs, TLS, rate limits, and a future OAuth/OIDC design before any "
            "remote or multi-user deployment."
        ),
    )


@dataclass
class _SlidingWindowRateLimiter:
    limit: int
    window_seconds: int
    requests: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def check(self, client_ip: str, *, limit: int | None = None) -> tuple[bool, int]:
        now = time.time()
        request_limit = limit if limit is not None else self.limit
        window = self.requests[client_ip]
        while window and now - window[0] >= self.window_seconds:
            window.popleft()
        if len(window) >= request_limit:
            retry_after = max(1, int(self.window_seconds - (now - window[0])))
            return True, retry_after
        window.append(now)
        return False, 0


def _parse_content_length(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


class _ToolBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes

    async def __call__(self, scope: ASGIScope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or not str(scope.get("path", "")).startswith("/tools/")
        ):
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                await self.app(scope, _replay_receive([message]), send)
                return
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_body_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={"detail": "Tool request body is too large."},
                )
                await response(scope, _empty_receive, send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break

        await self.app(
            scope,
            _replay_receive([{"type": "http.request", "body": b"".join(chunks)}]),
            send,
        )


def _replay_receive(messages: list[Message]) -> Receive:
    sent = False

    async def _receive() -> Message:
        nonlocal sent
        if sent or not messages:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return messages[0]

    return _receive


async def _empty_receive() -> Message:
    return {"type": "http.request", "body": b"", "more_body": False}
