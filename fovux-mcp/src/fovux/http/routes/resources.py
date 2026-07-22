"""FastAPI adapters for dataset and export ledger resources."""

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


@router.get("/datasets")
async def list_datasets(request: Request) -> JSONResponse:
    """List registered datasets."""
    return JSONResponse(_services(request).lineage.list_datasets())


@router.get("/datasets/{fingerprint}")
async def get_dataset(fingerprint: str, request: Request) -> JSONResponse:
    """Fetch one dataset by fingerprint."""
    try:
        return JSONResponse(_services(request).lineage.get_dataset(fingerprint))
    except ServiceError as error:
        _raise_http(error)


@router.get("/exports")
async def list_exports(request: Request) -> JSONResponse:
    """List recorded model exports."""
    return JSONResponse(_services(request).lineage.list_exports())
