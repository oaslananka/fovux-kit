"""FastAPI adapters for persistent background operations."""

from __future__ import annotations

import asyncio
from typing import Any, Never, cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from fovux.core.auth import ALL_SCOPES, is_known_session_token, resolve_session_scopes
from fovux.http.services.container import HttpServices
from fovux.http.services.errors import ServiceError
from fovux.http.services.operations import CreateOperationCommand, OperationService

router = APIRouter()


class CreateOperationInput(BaseModel):
    """Input parameters to create a background operation."""

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict, json_schema_extra={"default": {}})
    idempotency_key: str | None = None
    challenge_id: str | None = None


def _services(request: Request) -> HttpServices:
    return cast(HttpServices, request.app.state.http_services)


def _service(request: Request) -> OperationService:
    return _services(request).operations


def _raise_http(error: ServiceError) -> Never:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.post("/operations")
async def create_operation_route(
    request: Request,
    body: CreateOperationInput,
) -> JSONResponse:
    """Create a persistent background operation with an optional idempotency key."""
    services = _services(request)
    raw_token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    scopes = resolve_session_scopes(raw_token) if is_known_session_token(raw_token) else ALL_SCOPES
    command = CreateOperationCommand(
        tool=body.tool,
        arguments=body.arguments,
        idempotency_key=body.idempotency_key,
        challenge_id=body.challenge_id,
    )
    try:
        outcome = services.operations.create(
            services.operation_runtime,
            services.tool_runtime,
            scopes,
            command,
        )
    except ServiceError as error:
        _raise_http(error)
    return JSONResponse(status_code=outcome.status_code, content=outcome.payload)


@router.get("/operations/{id}")
async def get_operation_route(id: str, request: Request) -> JSONResponse:
    """Get status and metadata for a background operation."""
    try:
        return JSONResponse(_service(request).get(id))
    except ServiceError as error:
        _raise_http(error)


@router.post("/operations/{id}/cancel")
async def cancel_operation_route(id: str, request: Request) -> JSONResponse:
    """Request cancellation of a background operation."""
    services = _services(request)
    try:
        outcome = services.operations.cancel(services.operation_runtime, id)
    except ServiceError as error:
        _raise_http(error)
    return JSONResponse(status_code=outcome.status_code, content=outcome.payload)


@router.get("/operations/{id}/logs")
async def get_operation_logs_route(id: str, request: Request) -> StreamingResponse:
    """Fetch or stream execution logs for a background operation."""
    try:
        stream = _service(request).log_stream(id)
    except ServiceError as error:
        _raise_http(error)
    return StreamingResponse(
        stream,
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/operations/{id}/result")
async def get_operation_result_route(id: str, request: Request) -> JSONResponse:
    """Fetch the final result of a background operation."""
    try:
        outcome = _service(request).result(id)
    except ServiceError as error:
        _raise_http(error)
    return JSONResponse(status_code=outcome.status_code, content=outcome.payload)


@router.get("/events")
async def sse_events_route(request: Request) -> StreamingResponse:
    """Server-Sent Events (SSE) stream of all operations events with resume support."""
    services = _services(request)
    raw_last_id = request.headers.get("Last-Event-ID") or request.query_params.get("last_event_id")
    try:
        last_event_id = int(raw_last_id) if raw_last_id else None
    except ValueError:
        last_event_id = None
    shutdown_event = cast(asyncio.Event, request.app.state.shutdown_event)
    stream = services.operations.event_stream(
        services.operation_runtime,
        last_event_id=last_event_id,
        disconnect_check=request.is_disconnected,
        shutdown_event=shutdown_event,
    )
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
