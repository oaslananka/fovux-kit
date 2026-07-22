"""FastAPI adapters for run queries and metric streams."""

from __future__ import annotations

import asyncio
from typing import Never, cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from fovux.http.services.container import HttpServices
from fovux.http.services.errors import ServiceError
from fovux.http.services.runs import RunSearchFilters, RunService

router = APIRouter()


class RunsSearchInput(BaseModel):
    """Input payload for run search filters."""

    query: str | None = None
    tags: list[str] = Field(default_factory=list, json_schema_extra={"default": []})
    status: list[str] = Field(default_factory=list, json_schema_extra={"default": []})
    min_map50: float | None = None
    limit: int = 50


def _service(request: Request) -> RunService:
    services = cast(HttpServices, request.app.state.http_services)
    return services.runs


def _raise_http(error: ServiceError) -> Never:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/runs")
async def list_runs(request: Request) -> JSONResponse:
    """List all training runs."""
    return JSONResponse(_service(request).list_runs())


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request) -> JSONResponse:
    """Get metadata for a single run."""
    try:
        return JSONResponse(_service(request).get_run(run_id))
    except ServiceError as error:
        _raise_http(error)


@router.post("/runs/search")
async def search_runs(body: RunsSearchInput, request: Request) -> JSONResponse:
    """Search runs by text, tags, status, and minimum mAP50."""
    filters = RunSearchFilters(
        query=body.query,
        tags=tuple(body.tags),
        status=tuple(body.status),
        min_map50=body.min_map50,
        limit=body.limit,
    )
    return JSONResponse(_service(request).search_runs(filters))


@router.get("/runs/{run_id}/stream")
async def stream_run_metrics(run_id: str, request: Request) -> StreamingResponse:
    """Stream normalized metric rows for a run over server-sent events."""
    return _stream_response(run_id, request)


@router.get("/runs/{run_id}/metrics")
async def stream_run_metrics_compat(run_id: str, request: Request) -> StreamingResponse:
    """Compatibility alias for the canonical run metric stream."""
    return _stream_response(run_id, request)


def _stream_response(run_id: str, request: Request) -> StreamingResponse:
    service = _service(request)
    try:
        run_dir = service.resolve_run_dir(run_id)
    except ServiceError as error:
        _raise_http(error)
    shutdown_event = cast(asyncio.Event, request.app.state.shutdown_event)
    return StreamingResponse(
        service.metric_event_stream(
            run_id=run_id,
            run_dir=run_dir,
            disconnect_check=request.is_disconnected,
            shutdown_event=shutdown_event,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
