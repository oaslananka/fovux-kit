"""FastAPI adapters for challenge creation and local tool invocation."""

from __future__ import annotations

from typing import Never, cast

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse

from fovux.core.auth import token_fingerprint
from fovux.http.services.container import HttpServices
from fovux.http.services.errors import ServiceError
from fovux.http.services.tools import ToolInvocationContext

router = APIRouter()
_EMPTY_PAYLOAD = Body(default_factory=dict)


def _services(request: Request) -> HttpServices:
    return cast(HttpServices, request.app.state.http_services)


def _raise_http(error: ServiceError) -> Never:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post("/tools/{name}/challenge")
async def request_challenge(
    request: Request,
    name: str,
    payload: dict[str, object] = _EMPTY_PAYLOAD,
) -> JSONResponse:
    """Request an exact-payload confirmation challenge for a risky tool."""
    services = _services(request)
    try:
        outcome = services.challenges.request(services.tool_runtime, name, payload)
    except ServiceError as error:
        _raise_http(error)
    return JSONResponse(status_code=outcome.status_code, content=outcome.payload)


@router.post("/tools/{name}")
async def proxy_tool(
    request: Request,
    name: str,
    payload: dict[str, object] = _EMPTY_PAYLOAD,
) -> JSONResponse:
    """Invoke a policy-governed local Fovux tool."""
    services = _services(request)
    origin = request.headers.get("origin")
    if origin is None and request.client is not None:
        origin = request.client.host
    context = ToolInvocationContext(
        actor=token_fingerprint(str(request.app.state.auth_token)),
        origin=origin,
    )
    try:
        outcome = await services.tools.invoke(services.tool_runtime, context, name, payload)
    except ServiceError as error:
        _raise_http(error)
    return JSONResponse(status_code=outcome.status_code, content=outcome.payload)
