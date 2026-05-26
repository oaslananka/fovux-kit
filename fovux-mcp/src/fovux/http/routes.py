"""HTTP route definitions for fovux-studio integration.

Endpoints:
  GET  /runs                   — list all runs
  GET  /runs/{run_id}          — single run metadata
  GET  /runs/{run_id}/stream   — canonical SSE stream of metrics.jsonl lines
  GET  /runs/{run_id}/metrics  — compatibility SSE stream of metrics.jsonl lines
  POST /tools/{name}           — proxy to MCP tool call
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ValidationError
from watchfiles import Change, awatch

from fovux.core.checkpoints import (
    load_metrics_jsonl,
    normalize_metric_row,
    read_metric_rows,
    read_metrics_summary,
)
from fovux.core.errors import FovuxError
from fovux.core.logging import get_logger
from fovux.core.runs import RunRecord
from fovux.schemas.errors import ErrorDetail

router = APIRouter()
_EMPTY_PAYLOAD = Body(default_factory=dict)
_TOOL_OPERATION_RESULT_TTL_SECONDS = 300.0
_MAX_TOOL_OPERATION_RESULTS = 128


@router.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    from fovux import __version__

    return {"status": "ok", "version": __version__, "service": "fovux-mcp"}


@router.get("/runs")
async def list_runs() -> JSONResponse:
    """List all training runs."""
    from fovux.core.paths import ensure_fovux_dirs

    paths = ensure_fovux_dirs()
    from fovux.core.runs import get_registry

    registry = get_registry(paths.runs_db)
    records = registry.list_runs()
    return JSONResponse([_run_summary(record) for record in records])


def _run_summary(record: RunRecord) -> dict[str, object]:
    run_path = Path(str(record.run_path))
    status_payload = _read_status_payload(run_path)
    status = str(status_payload.get("status") or record.status)
    current_epoch, best_map50 = read_metrics_summary(run_path)
    return {
        "id": str(record.id),
        "status": status,
        "model": str(record.model),
        "epochs": int(record.epochs),
        "run_path": str(record.run_path),
        "current_epoch": current_epoch,
        "best_map50": best_map50,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _read_status_payload(run_dir: Path) -> dict[str, object]:
    status_file = run_dir / "status.json"
    if not status_file.exists():
        return {}
    try:
        payload = json.loads(status_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return cast(dict[str, object], payload)


@router.get("/metrics")
async def prometheus_metrics(request: Request) -> PlainTextResponse:
    """Expose a small Prometheus-compatible metrics snapshot when enabled."""
    if not bool(getattr(request.app.state, "metrics_enabled", False)):
        raise HTTPException(status_code=404, detail="Metrics endpoint is disabled.")

    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)
    records = registry.list_runs(limit=10000)
    active_runs = sum(1 for record in records if record.status == "running")
    total_runs = len(records)
    lines = [
        "# HELP fovux_active_runs Number of currently running Fovux training runs.",
        "# TYPE fovux_active_runs gauge",
        f"fovux_active_runs {active_runs}",
        "# HELP fovux_runs_total Number of runs tracked by the local registry.",
        "# TYPE fovux_runs_total gauge",
        f"fovux_runs_total {total_runs}",
    ]
    return PlainTextResponse("\n".join(lines) + "\n")


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> JSONResponse:
    """Get metadata for a single run."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)
    record = registry.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    run_path = Path(record.run_path)
    status_payload = _read_status_payload(run_path)
    status = str(status_payload.get("status") or record.status)
    current_epoch, best_map50 = read_metrics_summary(run_path)
    return JSONResponse(
        {
            "id": record.id,
            "status": status,
            "model": record.model,
            "dataset_path": record.dataset_path,
            "task": record.task,
            "epochs": record.epochs,
            "pid": record.pid,
            "run_path": record.run_path,
            "current_epoch": current_epoch,
            "best_map50": best_map50,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "finished_at": record.finished_at.isoformat() if record.finished_at else None,
        }
    )


class RunsSearchInput(BaseModel):
    """Input payload for run search filters."""

    query: str | None = None
    tags: list[str] = []
    status: list[str] = []
    min_map50: float | None = None
    limit: int = 50


@router.post("/runs/search")
async def search_runs(body: RunsSearchInput) -> JSONResponse:
    """Search runs by text, tags, status, and minimum mAP50."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)
    records = registry.list_runs(limit=max(body.limit, 1) * 4)

    matched: list[dict[str, object]] = []
    lowered_query = body.query.lower() if body.query else None
    required_statuses = {status.lower() for status in body.status}
    required_tags = {tag.lower() for tag in body.tags}

    for record in records:
        raw_tags = cast(str, record.tags_json or "[]")
        record_tags = {str(tag).lower() for tag in json.loads(raw_tags)}
        haystack = " ".join(
            [
                str(record.id),
                str(record.model),
                str(record.dataset_path),
                str(record.task),
                " ".join(record_tags),
                str(record.extra_json or ""),
            ]
        ).lower()
        if lowered_query and lowered_query not in haystack:
            continue
        if required_statuses and str(record.status).lower() not in required_statuses:
            continue
        if required_tags and not required_tags.issubset(record_tags):
            continue
        _, best_map50 = read_metrics_summary(Path(record.run_path))
        if body.min_map50 is not None and (best_map50 is None or best_map50 < body.min_map50):
            continue
        matched.append(
            {
                "id": record.id,
                "status": record.status,
                "model": record.model,
                "dataset_path": record.dataset_path,
                "task": record.task,
                "epochs": record.epochs,
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "best_map50": best_map50,
                "tags": sorted(record_tags),
            }
        )
        if len(matched) >= body.limit:
            break
    return JSONResponse(matched)


@router.get("/runs/{run_id}/stream")
async def stream_run_metrics(run_id: str, request: Request) -> StreamingResponse:
    """Stream normalized metric rows for a run over server-sent events."""
    return _stream_run_metrics_response(run_id, request)


@router.get("/runs/{run_id}/metrics")
async def stream_run_metrics_compat(run_id: str, request: Request) -> StreamingResponse:
    """Compatibility alias for the canonical run metric stream."""
    return _stream_run_metrics_response(run_id, request)


def _stream_run_metrics_response(run_id: str, request: Request) -> StreamingResponse:
    run_dir = _resolve_run_dir(run_id)
    shutdown_event = cast(asyncio.Event, request.app.state.shutdown_event)

    return StreamingResponse(
        _metric_event_stream(
            run_id=run_id,
            run_dir=run_dir,
            disconnect_check=request.is_disconnected,
            shutdown_event=shutdown_event,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _release_semaphore_after_worker(
    semaphore: asyncio.Semaphore,
) -> Callable[[asyncio.Future[Any]], None]:
    logger = get_logger(__name__)

    def _release(task: asyncio.Future[Any]) -> None:
        try:
            error = task.exception()
        except asyncio.CancelledError:
            error = None
        except Exception as exc:  # defensive: done callbacks must not raise into the event loop
            logger.warning(
                "http_tool_worker_exception_inspection_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        else:
            if error is not None:
                logger.error(
                    "http_tool_worker_failed_after_timeout",
                    error_type=type(error).__name__,
                    error=str(error),
                )
        finally:
            semaphore.release()

    return _release


def _tool_operation_id(tool: str, args_hash: str) -> str:
    return f"{tool}-{args_hash}"


def _remember_timed_out_tool_worker(
    *,
    semaphore: asyncio.Semaphore,
    operations: dict[str, asyncio.Future[Any]],
    results: dict[str, dict[str, object]],
    operation_key: str,
    operation_id: str,
) -> Callable[[asyncio.Future[Any]], None]:
    logger = get_logger(__name__)

    def _complete(task: asyncio.Future[Any]) -> None:
        try:
            error = task.exception()
        except asyncio.CancelledError:
            error = None
            results[operation_key] = {
                "operation_id": operation_id,
                "status": "cancelled",
                "finished_at": time.monotonic(),
            }
        except Exception as exc:  # defensive: done callbacks must not raise into the event loop
            error = exc
            logger.warning(
                "http_tool_worker_exception_inspection_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
        else:
            if error is None:
                try:
                    result = task.result()
                except Exception as exc:  # defensive: task.exception() should have seen this
                    error = exc
                else:
                    results[operation_key] = {
                        "operation_id": operation_id,
                        "status": "succeeded",
                        "result": result,
                        "finished_at": time.monotonic(),
                    }
            if error is not None:
                results[operation_key] = {
                    "operation_id": operation_id,
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "finished_at": time.monotonic(),
                }
                logger.error(
                    "http_tool_worker_failed_after_timeout",
                    error_type=type(error).__name__,
                    error=str(error),
                )
        finally:
            operations.pop(operation_key, None)
            _prune_tool_operation_results(results)
            semaphore.release()

    return _complete


def _pop_fresh_tool_operation_result(
    results: dict[str, dict[str, object]],
    operation_key: str,
) -> dict[str, object] | None:
    result = results.get(operation_key)
    if result is None:
        return None
    finished_at = result.get("finished_at")
    if not isinstance(finished_at, int | float):
        results.pop(operation_key, None)
        return None
    if time.monotonic() - float(finished_at) > _TOOL_OPERATION_RESULT_TTL_SECONDS:
        results.pop(operation_key, None)
        return None
    return result


def _prune_tool_operation_results(results: dict[str, dict[str, object]]) -> None:
    now = time.monotonic()
    for key, result in list(results.items()):
        finished_at = result.get("finished_at")
        if not isinstance(finished_at, int | float):
            results.pop(key, None)
            continue
        if now - float(finished_at) > _TOOL_OPERATION_RESULT_TTL_SECONDS:
            results.pop(key, None)
    if len(results) <= _MAX_TOOL_OPERATION_RESULTS:
        return
    oldest = sorted(
        results.items(),
        key=lambda item: float(cast(int | float, item[1].get("finished_at", 0))),
    )
    for key, _result in oldest[: len(results) - _MAX_TOOL_OPERATION_RESULTS]:
        results.pop(key, None)


@router.post("/tools/{name}")
async def proxy_tool(
    request: Request,
    name: str,
    payload: dict[str, object] = _EMPTY_PAYLOAD,
) -> JSONResponse:
    """Invoke a local Fovux tool through the HTTP transport."""
    from fovux.core.auth import token_fingerprint
    from fovux.http.tool_proxy import (
        HttpToolPolicyError,
        invoke_tool,
        payload_hash,
        policy_for_tool,
    )

    logger = get_logger(__name__)
    origin = request.headers.get("origin")
    if origin is None and request.client is not None:
        origin = request.client.host
    actor = token_fingerprint(str(request.app.state.auth_token))
    args_hash = payload_hash(payload)
    operation_id = _tool_operation_id(name, args_hash)
    operation_key = f"{name}:{args_hash}"
    started = time.monotonic()
    try:
        policy = policy_for_tool(name)
        semaphores = cast(dict[str, asyncio.Semaphore], request.app.state.tool_semaphores)
        semaphore = semaphores[name]
        operations = cast(dict[str, asyncio.Future[Any]], request.app.state.tool_operations)
        operation_results = cast(
            dict[str, dict[str, object]],
            request.app.state.tool_operation_results,
        )
        _prune_tool_operation_results(operation_results)
        completed_operation = _pop_fresh_tool_operation_result(operation_results, operation_key)
        if completed_operation is not None:
            if completed_operation.get("status") == "succeeded":
                result = cast(dict[str, Any], completed_operation.get("result") or {})
                logger.info(
                    "http_tool_audit",
                    actor=actor,
                    origin=origin,
                    tool=name,
                    args_hash=args_hash,
                    status="success",
                    duration_ms=int((time.monotonic() - started) * 1000),
                    failure_class=None,
                )
                return JSONResponse(result)
            logger.warning(
                "http_tool_audit",
                actor=actor,
                origin=origin,
                tool=name,
                args_hash=args_hash,
                status="failed",
                duration_ms=int((time.monotonic() - started) * 1000),
                failure_class="background_operation_failed",
            )
            return JSONResponse(
                status_code=500,
                content={
                    "operation_id": completed_operation.get("operation_id", operation_id),
                    "status": completed_operation.get("status", "failed"),
                    "error_type": completed_operation.get("error_type"),
                    "error": completed_operation.get("error"),
                },
            )
        running_operation = operations.get(operation_key)
        if running_operation is not None and not running_operation.done():
            logger.info(
                "http_tool_audit",
                actor=actor,
                origin=origin,
                tool=name,
                args_hash=args_hash,
                status="accepted",
                duration_ms=int((time.monotonic() - started) * 1000),
                failure_class=None,
            )
            return JSONResponse(
                status_code=202,
                content={
                    "operation_id": operation_id,
                    "status": "running",
                    "message": "Tool execution is still running.",
                },
            )
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=0.01)
        except TimeoutError as exc:
            logger.warning(
                "http_tool_audit",
                actor=actor,
                origin=origin,
                tool=name,
                args_hash=args_hash,
                status="rejected",
                duration_ms=0,
                failure_class="concurrency_limit",
            )
            raise HTTPException(status_code=429, detail="Tool concurrency limit exceeded.") from exc
        release_deferred = False
        try:
            worker_task = asyncio.create_task(asyncio.to_thread(invoke_tool, name, payload))
            try:
                result = await asyncio.wait_for(
                    asyncio.shield(worker_task),
                    timeout=policy.timeout_seconds,
                )
            except TimeoutError:
                operations[operation_key] = worker_task
                worker_task.add_done_callback(
                    _remember_timed_out_tool_worker(
                        semaphore=semaphore,
                        operations=operations,
                        results=operation_results,
                        operation_key=operation_key,
                        operation_id=operation_id,
                    )
                )
                release_deferred = True
                logger.warning(
                    "http_tool_audit",
                    actor=actor,
                    origin=origin,
                    tool=name,
                    args_hash=args_hash,
                    status="accepted",
                    duration_ms=int((time.monotonic() - started) * 1000),
                    failure_class="background_operation",
                )
                return JSONResponse(
                    status_code=202,
                    content={
                        "operation_id": operation_id,
                        "status": "running",
                        "message": (
                            "Tool execution exceeded the request timeout and continues once."
                        ),
                    },
                )
        finally:
            if not release_deferred:
                semaphore.release()
    except TimeoutError as exc:
        logger.warning(
            "http_tool_audit",
            actor=actor,
            origin=origin,
            tool=name,
            args_hash=args_hash,
            status="failed",
            duration_ms=int((time.monotonic() - started) * 1000),
            failure_class="timeout",
        )
        raise HTTPException(status_code=504, detail="Tool execution timed out.") from exc
    except HttpToolPolicyError as exc:
        logger.warning(
            "http_tool_audit",
            actor=actor,
            origin=origin,
            tool=name,
            args_hash=args_hash,
            status="rejected",
            duration_ms=int((time.monotonic() - started) * 1000),
            failure_class="policy",
        )
        detail = ErrorDetail(code=exc.code, message=exc.message, hint=exc.hint)
        raise HTTPException(status_code=403, detail=detail.model_dump(mode="json")) from exc
    except ValidationError as exc:
        logger.warning(
            "http_tool_audit",
            actor=actor,
            origin=origin,
            tool=name,
            args_hash=args_hash,
            status="failed",
            duration_ms=int((time.monotonic() - started) * 1000),
            failure_class="validation_error",
        )
        detail = ErrorDetail(
            code="FOVUX_HTTP_002",
            message="Tool payload validation failed.",
            hint=str(exc),
        )
        raise HTTPException(status_code=422, detail=detail.model_dump(mode="json")) from exc
    except FovuxError as exc:
        logger.warning(
            "http_tool_audit",
            actor=actor,
            origin=origin,
            tool=name,
            args_hash=args_hash,
            status="failed",
            duration_ms=int((time.monotonic() - started) * 1000),
            failure_class=exc.code,
        )
        detail = ErrorDetail(code=exc.code, message=exc.message, hint=exc.hint)
        raise HTTPException(
            status_code=400,
            detail=detail.model_dump(mode="json"),
        ) from exc

    logger.info(
        "http_tool_audit",
        actor=actor,
        origin=origin,
        tool=name,
        args_hash=args_hash,
        status="success",
        duration_ms=int((time.monotonic() - started) * 1000),
        failure_class=None,
    )
    return JSONResponse(result)


def _resolve_run_dir(run_id: str) -> Path:
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)
    record = registry.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    return Path(record.run_path)


async def _metric_event_stream(
    *,
    run_id: str,
    run_dir: Path,
    disconnect_check: Callable[[], Awaitable[bool]],
    shutdown_event: asyncio.Event,
) -> AsyncIterator[str]:
    yield "retry: 5000\n\n"

    metrics_jsonl = run_dir / "metrics.jsonl"
    jsonl_offset = 0
    emitted_count = 0
    snapshot = _load_metric_payloads(run_id, run_dir)
    for payload in snapshot:
        yield f"event: metric\ndata: {json.dumps(payload)}\n\n"
    emitted_count = len(snapshot)
    if metrics_jsonl.exists():
        jsonl_offset = metrics_jsonl.stat().st_size
    if _is_terminal_run(run_dir):
        yield "event: done\ndata: {}\n\n"
        return

    watcher = awatch(run_dir, stop_event=shutdown_event, debounce=150)
    last_heartbeat = time.monotonic()

    while not shutdown_event.is_set():
        if await disconnect_check():
            get_logger(__name__).info("metrics_stream_disconnected", run_id=run_id)
            break

        try:
            changes = await asyncio.wait_for(watcher.__anext__(), timeout=15.0)
        except TimeoutError:
            yield ": keep-alive\n\n"
            last_heartbeat = time.monotonic()
            continue
        except StopAsyncIteration:
            break

        delta_payloads: list[dict[str, object]]
        if _contains_metrics_jsonl_change(changes):
            emitted_count, jsonl_offset, delta_payloads = _load_metric_payload_delta(
                run_id, run_dir, emitted_count, jsonl_offset
            )
        else:
            delta_payloads = _load_metric_payloads(run_id, run_dir)[emitted_count:]
            emitted_count += len(delta_payloads)

        for payload in delta_payloads:
            yield f"event: metric\ndata: {json.dumps(payload)}\n\n"
            last_heartbeat = time.monotonic()

        if _is_terminal_run(run_dir):
            yield "event: done\ndata: {}\n\n"
            break

        if time.monotonic() - last_heartbeat >= 15.0:
            yield ": keep-alive\n\n"
            last_heartbeat = time.monotonic()


def _load_metric_payloads(run_id: str, run_dir: Path) -> list[dict[str, object]]:
    payloads = load_metrics_jsonl(run_dir)
    if payloads:
        return payloads
    rows = read_metric_rows(run_dir)
    return [normalize_metric_row(run_id, row) for row in rows]


def _load_metrics_jsonl(run_id: str, run_dir: Path) -> list[dict[str, object]]:
    del run_id
    return load_metrics_jsonl(run_dir)


def _contains_metrics_jsonl_change(changes: set[tuple[Change, str]]) -> bool:
    for _, changed_path in changes:
        if Path(changed_path).name == "metrics.jsonl":
            return True
    return False


def _load_metric_payload_delta(
    run_id: str,
    run_dir: Path,
    emitted_count: int,
    previous_offset: int,
) -> tuple[int, int, list[dict[str, object]]]:
    metrics_path = run_dir / "metrics.jsonl"
    if not metrics_path.exists():
        full_payloads = _load_metric_payloads(run_id, run_dir)
        new_payloads = full_payloads[emitted_count:]
        return emitted_count + len(new_payloads), previous_offset, new_payloads

    current_size = metrics_path.stat().st_size
    if current_size < previous_offset:
        refreshed_payloads = load_metrics_jsonl(run_dir)
        return len(refreshed_payloads), current_size, refreshed_payloads

    if current_size == previous_offset:
        return emitted_count, previous_offset, []

    with metrics_path.open("r", encoding="utf-8") as handle:
        handle.seek(previous_offset)
        lines = handle.read().splitlines()

    delta_payloads: list[dict[str, object]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            raw = cast(dict[str, object], json.loads(line))
        except json.JSONDecodeError:
            continue
        metrics = raw.get("metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}
        epoch_value = raw.get("epoch", emitted_count + len(delta_payloads) + 1)
        delta_payloads.append(
            {
                "runId": str(raw.get("run_id", run_id)),
                "epoch": int(epoch_value) if isinstance(epoch_value, int | float | str) else 0,
                "metrics": {
                    str(key): float(value)
                    for key, value in metrics.items()
                    if isinstance(value, int | float)
                },
            }
        )
    return emitted_count + len(delta_payloads), current_size, delta_payloads


def _is_terminal_run(run_dir: Path) -> bool:
    status = str(_read_status_payload(run_dir).get("status", "")).lower()
    return status in {"complete", "completed", "failed", "stopped"}
