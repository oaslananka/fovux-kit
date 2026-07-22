"""Domain router aggregation and compatibility exports for the local HTTP API."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter

from fovux.core.logging import get_logger
from fovux.http.routes.health import router as health_router
from fovux.http.routes.lineage import router as lineage_router
from fovux.http.routes.operations import router as operations_router
from fovux.http.routes.operations import sse_events_route
from fovux.http.routes.resources import router as resources_router
from fovux.http.routes.runs import router as runs_router
from fovux.http.routes.tools import router as tools_router
from fovux.http.services.runs import (
    RunService,
    _load_metric_payload_delta,
    _load_metric_payloads,
    _load_metrics_jsonl,
    _metric_event_stream,
)
from fovux.http.services.tool_runtime import (
    pop_fresh_tool_operation_result as _pop_fresh_tool_operation_result,
)
from fovux.http.services.tool_runtime import (
    prune_tool_operation_results as _prune_tool_operation_results,
)
from fovux.http.services.tool_runtime import (
    release_semaphore_after_worker as _release_semaphore_after_worker,
)
from fovux.http.services.tool_runtime import (
    remember_timed_out_tool_worker as _remember_timed_out_tool_worker,
)


def build_http_router() -> APIRouter:
    """Assemble every domain router exactly once."""
    root = APIRouter()
    for domain_router in (
        health_router,
        runs_router,
        tools_router,
        operations_router,
        lineage_router,
        resources_router,
    ):
        root.include_router(domain_router)
    return root


def _resolve_run_dir(run_id: str) -> Path:
    """Compatibility wrapper for the historical internal helper."""
    return RunService().resolve_run_dir(run_id)


def _tool_operation_id(tool: str, args_hash: str) -> str:
    """Compatibility wrapper for historical operation identifiers."""
    return f"{tool}-{args_hash}"


router = build_http_router()

__all__ = [
    "_load_metric_payload_delta",
    "_load_metric_payloads",
    "_load_metrics_jsonl",
    "_metric_event_stream",
    "_pop_fresh_tool_operation_result",
    "_prune_tool_operation_results",
    "_release_semaphore_after_worker",
    "_remember_timed_out_tool_worker",
    "_resolve_run_dir",
    "_tool_operation_id",
    "asyncio",
    "build_http_router",
    "get_logger",
    "router",
    "sse_events_route",
]
