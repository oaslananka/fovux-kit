"""FastAPI adapters for run lineage and lifecycle events."""

from __future__ import annotations

from typing import Never, cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from fovux.http.services.container import HttpServices
from fovux.http.services.errors import ServiceError

router = APIRouter()


def _services(request: Request) -> HttpServices:
    return cast(HttpServices, request.app.state.http_services)


def _raise_http(error: ServiceError) -> Never:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/runs/{run_id}/lineage")
async def get_run_lineage(run_id: str, request: Request) -> JSONResponse:
    """Fetch experiment lineage information for a run."""
    try:
        return JSONResponse(_services(request).lineage.run_lineage(run_id))
    except ServiceError as error:
        _raise_http(error)


@router.get("/runs/{run_id}/events")
async def get_run_events(run_id: str, request: Request) -> JSONResponse:
    """Fetch all lifecycle and audit events for a single run."""
    try:
        return JSONResponse(_services(request).lineage.run_events(run_id))
    except ServiceError as error:
        _raise_http(error)
