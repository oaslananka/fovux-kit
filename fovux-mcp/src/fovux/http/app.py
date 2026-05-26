"""FastAPI application for optional HTTP transport.

Provides REST endpoints for fovux-studio to query run state and stream
live metrics. Binds to 127.0.0.1 by default.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from fovux import __version__
from fovux.core.auth import auth_token_path, ensure_auth_token, token_fingerprint
from fovux.core.logging import get_logger

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
DEFAULT_TOOL_RATE_LIMIT = 100
TOOL_RATE_LIMITS = {"train_start": 5}
MAX_TOOL_BODY_BYTES = 1024 * 1024


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
        title="Fovux MCP HTTP Transport",
        version=__version__,
        description="Local HTTP interface for fovux-studio VS Code extension.",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^(vscode-webview://.*|https://.*\.vscode-cdn\.net)$",
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )
    app.add_middleware(_ToolBodyLimitMiddleware, max_body_bytes=MAX_TOOL_BODY_BYTES)
    app.state.metrics_enabled = enable_metrics
    app.state.tool_body_max_bytes = MAX_TOOL_BODY_BYTES
    from fovux.http.tool_proxy import HTTP_TOOL_POLICIES

    app.state.tool_semaphores = {
        name: asyncio.Semaphore(policy.concurrency_limit)
        for name, policy in HTTP_TOOL_POLICIES.items()
        if policy.enabled
    }
    app.state.tool_operations = {}
    app.state.tool_operation_results = {}

    @app.middleware("http")
    async def _auth_and_rate_limit(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if (
            request.method.upper() == "OPTIONS"
            and request.headers.get("Origin")
            and request.headers.get("Access-Control-Request-Method")
        ):
            return await call_next(request)

        if request.url.path != "/health":
            token = request.app.state.auth_token
            auth_header = request.headers.get("Authorization", "")
            if auth_header != f"Bearer {token}":
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing or invalid bearer token."},
                )

            if request.method.upper() == "POST" and request.url.path.startswith("/tools/"):
                content_length = _parse_content_length(request.headers.get("content-length"))
                if content_length is not None and content_length > MAX_TOOL_BODY_BYTES:
                    return JSONResponse(
                        status_code=413,
                        content={"detail": "Tool request body is too large."},
                    )
                client_ip = request.client.host if request.client is not None else "unknown"
                tool_name = request.url.path.removeprefix("/tools/").split("/", maxsplit=1)[0]
                limit = TOOL_RATE_LIMITS.get(tool_name, DEFAULT_TOOL_RATE_LIMIT)
                limited, retry_after = request.app.state.rate_limiter.check(
                    f"{client_ip}:tool:{tool_name}",
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
    return app


def warn_if_nonlocal_host(host: str) -> None:
    """Log a warning when HTTP is configured for a non-local bind host."""
    if host.lower() in _LOCAL_HOSTS:
        return
    get_logger(__name__).warning(
        "http_nonlocal_bind",
        host=host,
        message=(
            "Fovux HTTP auth is local-first. If this bind is behind a reverse proxy, "
            "ensure the proxy is private and rate limiting remains effective."
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

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
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
