"""FastAPI adapters for health and Prometheus snapshots."""

from __future__ import annotations

from typing import Never, cast

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

from fovux.http.services.container import HttpServices
from fovux.http.services.errors import ServiceError

router = APIRouter()


def _services(request: Request) -> HttpServices:
    return cast(HttpServices, request.app.state.http_services)


def _raise_http(error: ServiceError) -> Never:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/health")
async def health(request: Request) -> dict[str, str]:
    """Health check endpoint."""
    return _services(request).health.health()


@router.get("/metrics")
async def prometheus_metrics(request: Request) -> PlainTextResponse:
    """Expose a small Prometheus-compatible metrics snapshot when enabled."""
    try:
        body = _services(request).health.prometheus_metrics(
            enabled=bool(getattr(request.app.state, "metrics_enabled", False))
        )
    except ServiceError as error:
        _raise_http(error)
    return PlainTextResponse(body)
