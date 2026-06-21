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
from fovux.core.runs import OperationRecord, RunRecord
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


@router.post("/tools/{name}/challenge")
async def request_challenge(
    request: Request,
    name: str,
    payload: dict[str, object] = _EMPTY_PAYLOAD,
) -> JSONResponse:
    """Request a confirmation challenge for a risky tool call.

    Returns a challenge_id that must be included when calling the tool
    via POST /tools/{name}. Read-only tools do not require challenges.
    """
    from fovux.http.challenge import create_challenge, prune_expired_challenges
    from fovux.http.tool_proxy import (
        HttpToolPolicyError,
        payload_hash,
        policy_for_tool,
    )

    try:
        policy = policy_for_tool(name)
    except HttpToolPolicyError as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "code": exc.code,
                "message": exc.message,
                "hint": exc.hint,
            },
        ) from exc
    if not policy.requires_confirmation:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FOVUX_HTTP_003",
                "message": f"Tool '{name}' does not require a confirmation challenge.",
                "hint": "Read-only tools can be called directly without a challenge.",
            },
        )

    challenges = cast(dict[str, Any], request.app.state.challenges)
    prune_expired_challenges(challenges)
    args_hash = payload_hash(payload)

    record = create_challenge(
        tool_name=name,
        args_hash=args_hash,
        risk_level=policy.category,
    )
    challenges[record.challenge_id] = record

    return JSONResponse(
        status_code=201,
        content={
            "challenge_id": record.challenge_id,
            "tool": name,
            "risk_level": policy.category,
            "summary": {
                "name": name,
                "args_hash": args_hash,
                "params": {
                    str(k): v
                    for k, v in payload.items()
                    if str(k) not in ("confirm", "challenge_id")
                },
            },
            "expires_at": record.expires_at,
        },
    )


@router.post("/tools/{name}")
async def proxy_tool(
    request: Request,
    name: str,
    payload: dict[str, object] = _EMPTY_PAYLOAD,
) -> JSONResponse:
    """Invoke a local Fovux tool through the HTTP transport.

    Tools that require confirmation must include a valid challenge_id
    obtained from POST /tools/{name}/challenge.
    """
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
    from fovux.http.challenge import prune_expired_challenges, verify_challenge

    started = time.monotonic()
    try:
        policy = policy_for_tool(name)
        if policy.requires_confirmation:
            challenges = cast(dict[str, Any], request.app.state.challenges)
            prune_expired_challenges(challenges)
            challenge_id = payload.get("challenge_id")
            if not isinstance(challenge_id, str) or not challenge_id.strip():
                raise HttpToolPolicyError(
                    f"Tool '{name}' requires a confirmation challenge.",
                    hint=(
                        "Call POST /tools/{name}/challenge first, then include the "
                        "returned challenge_id in the tool payload."
                    ),
                )
            challenge_payload = {k: v for k, v in payload.items() if k != "challenge_id"}
            verify_challenge(
                challenges,
                challenge_id=challenge_id,
                tool_name=name,
                args_hash=payload_hash(challenge_payload),
            )

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


# --- Operations Layer Endpoints and Background Logic ---


class CreateOperationInput(BaseModel):
    """Input parameters to create a background operation."""

    tool: str
    arguments: dict[str, Any] = {}
    idempotency_key: str | None = None
    challenge_id: str | None = None


def _operation_summary(record: OperationRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "idempotency_key": record.idempotency_key,
        "tool": record.tool,
        "status": record.status,
        "progress": record.progress,
        "error_type": record.error_type,
        "error": record.error,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "started_at": record.started_at.isoformat() if record.started_at else None,
        "finished_at": record.finished_at.isoformat() if record.finished_at else None,
        "run_id": record.run_id,
    }


def _notify_sse_listeners(
    app_state: Any,  # noqa: ANN401
    op_id: str,
    event_type: str,
    data: dict[str, Any],
) -> None:
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)

    event_payload = {
        "operation_id": op_id,
        "event_type": event_type,
        "data": data,
    }
    event_rec = registry.create_operation_event(op_id, event_type, event_payload)

    listeners = getattr(app_state, "sse_listeners", [])
    for queue in list(listeners):
        try:
            queue.put_nowait((event_rec.id, event_type, event_payload))
        except Exception:  # noqa: S110
            pass


async def _run_operation_in_background(
    op_id: str,
    tool_name: str,
    payload: dict[str, Any],
    semaphore: asyncio.Semaphore,
    app_state: Any,  # noqa: ANN401
) -> None:
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry
    from fovux.http.tool_proxy import invoke_tool

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)

    registry.update_operation_status(op_id, "running")
    registry.create_operation_event(op_id, "status_change", {"status": "running"})
    _notify_sse_listeners(app_state, op_id, "status_change", {"status": "running"})

    log_dir = paths.home / "operations"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{op_id}.log"

    await semaphore.acquire()

    def target() -> dict[str, Any]:
        from fovux.http.app import _thread_local

        with open(log_file, "a", encoding="utf-8") as f:
            _thread_local.stream = f
            try:
                f.write(
                    f"--- Operation {op_id} started at {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
                f.flush()
                res = invoke_tool(tool_name, payload)
                return res
            finally:
                f.write(f"--- Operation {op_id} finished ---\n")
                f.flush()
                _thread_local.stream = None

    try:
        worker_task = asyncio.create_task(asyncio.to_thread(target))
        app_state.active_operation_tasks[op_id] = worker_task

        result = await worker_task

        run_id = None
        if isinstance(result, dict) and "run_id" in result:
            run_id = str(result["run_id"])

        registry.update_operation_status(op_id, "succeeded", result=result, run_id=run_id)
        registry.create_operation_event(
            op_id,
            "status_change",
            {"status": "succeeded", "result": result, "run_id": run_id},
        )
        _notify_sse_listeners(
            app_state,
            op_id,
            "status_change",
            {"status": "succeeded", "result": result, "run_id": run_id},
        )
    except asyncio.CancelledError:
        registry.update_operation_status(op_id, "cancelled")
        registry.create_operation_event(op_id, "status_change", {"status": "cancelled"})
        _notify_sse_listeners(app_state, op_id, "status_change", {"status": "cancelled"})
        raise
    except Exception as exc:
        err_msg = str(exc)
        err_type = type(exc).__name__
        registry.update_operation_status(op_id, "failed", error_type=err_type, error=err_msg)
        registry.create_operation_event(
            op_id,
            "status_change",
            {"status": "failed", "error_type": err_type, "error": err_msg},
        )
        _notify_sse_listeners(
            app_state,
            op_id,
            "status_change",
            {"status": "failed", "error_type": err_type, "error": err_msg},
        )
    finally:
        semaphore.release()
        app_state.active_operation_tasks.pop(op_id, None)


@router.post("/operations")
async def create_operation_route(
    request: Request,
    body: CreateOperationInput,
) -> JSONResponse:
    """Create a persistent background operation with an optional idempotency key."""
    import uuid

    from fovux.core.auth import ALL_SCOPES, is_known_session_token, resolve_session_scopes
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry
    from fovux.http.challenge import prune_expired_challenges, verify_challenge
    from fovux.http.tool_proxy import check_scope, payload_hash, policy_for_tool

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)

    auth_header = request.headers.get("Authorization", "")
    raw_token = auth_header.removeprefix("Bearer ").strip()
    scopes = ALL_SCOPES
    if is_known_session_token(raw_token):
        scopes = resolve_session_scopes(raw_token)

    policy = policy_for_tool(body.tool)
    check_scope(policy, scopes)

    if policy.requires_confirmation:
        challenges = cast(dict[str, Any], request.app.state.challenges)
        prune_expired_challenges(challenges)
        challenge_id = body.challenge_id or body.arguments.get("challenge_id")
        if not isinstance(challenge_id, str) or not challenge_id.strip():
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FOVUX_HTTP_001",
                    "message": f"Tool '{body.tool}' requires a confirmation challenge.",
                    "hint": (
                        "Call POST /tools/{name}/challenge first, then include the challenge_id."
                    ),
                },
            )
        verify_challenge(
            challenges,
            challenge_id=challenge_id,
            tool_name=body.tool,
            args_hash=payload_hash(
                {k: v for k, v in body.arguments.items() if k != "challenge_id"}
            ),
        )

    if body.idempotency_key:
        existing = registry.get_operation_by_idempotency_key(body.idempotency_key)
        if existing is not None:
            return JSONResponse(
                status_code=200,
                content=_operation_summary(existing),
            )

    op_id = f"op_{uuid.uuid4().hex[:12]}"
    record = registry.create_operation(
        op_id=op_id,
        tool=body.tool,
        arguments=body.arguments,
        idempotency_key=body.idempotency_key,
    )

    semaphores = cast(dict[str, asyncio.Semaphore], request.app.state.tool_semaphores)
    semaphore = semaphores[body.tool]

    if not hasattr(request.app.state, "active_operation_tasks"):
        request.app.state.active_operation_tasks = {}

    task = asyncio.create_task(
        _run_operation_in_background(
            op_id=op_id,
            tool_name=body.tool,
            payload=body.arguments,
            semaphore=semaphore,
            app_state=request.app.state,
        )
    )
    request.app.state.active_operation_tasks[op_id] = task

    registry.create_operation_event(op_id, "status_change", {"status": "pending"})

    return JSONResponse(
        status_code=201,
        content=_operation_summary(record),
    )


@router.get("/operations/{id}")
async def get_operation_route(id: str) -> JSONResponse:
    """Get status and metadata for a background operation."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)

    record = registry.get_operation(id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Operation {id} not found.")

    return JSONResponse(_operation_summary(record))


@router.post("/operations/{id}/cancel")
async def cancel_operation_route(id: str, request: Request) -> JSONResponse:
    """Request cancellation of a background operation."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)

    record = registry.get_operation(id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Operation {id} not found.")

    if record.status in ("succeeded", "failed", "cancelled"):
        return JSONResponse(
            status_code=200,
            content=_operation_summary(record),
        )

    tasks = getattr(request.app.state, "active_operation_tasks", {})
    task = tasks.get(id)
    if task is not None:
        task.cancel()

    if record.run_id:
        from fovux.tools.train_stop import train_stop

        try:
            train_stop(run_id=str(record.run_id))
        except Exception:  # noqa: S110
            pass

    registry.update_operation_status(id, "cancelled")
    registry.create_operation_event(id, "status_change", {"status": "cancelled"})
    _notify_sse_listeners(request.app.state, id, "status_change", {"status": "cancelled"})

    record = registry.get_operation(id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Operation {id} not found.")
    return JSONResponse(
        status_code=200,
        content=_operation_summary(record),
    )


@router.get("/operations/{id}/logs")
async def get_operation_logs_route(id: str) -> StreamingResponse:
    """Fetch or stream execution logs for a background operation."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)

    record = registry.get_operation(id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Operation {id} not found.")

    log_file = paths.home / "operations" / f"{id}.log"
    if record.run_id:
        run_log = paths.home / "runs" / record.run_id / "stdout.log"
        if run_log.exists():
            log_file = run_log

    async def log_generator() -> AsyncIterator[str]:
        for _ in range(20):
            if log_file.exists():
                break
            await asyncio.sleep(0.1)

        if not log_file.exists():
            yield "Log file not found.\n"
            return

        with open(log_file, encoding="utf-8", errors="replace") as f:
            while True:
                line = f.readline()
                if line:
                    yield line
                else:
                    op = registry.get_operation(id)
                    if op is None or op.status in ("succeeded", "failed", "cancelled"):
                        remaining = f.read()
                        if remaining:
                            yield remaining
                        break
                    await asyncio.sleep(0.5)

    return StreamingResponse(
        log_generator(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/operations/{id}/result")
async def get_operation_result_route(id: str) -> JSONResponse:
    """Fetch the final result of a background operation."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)

    record = registry.get_operation(id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Operation {id} not found.")

    if record.status == "succeeded":
        res = {}
        if record.result_json:
            res = json.loads(str(record.result_json))
        return JSONResponse(res)
    elif record.status == "failed":
        return JSONResponse(
            status_code=500,
            content={
                "operation_id": record.id,
                "status": record.status,
                "error_type": record.error_type,
                "error": record.error,
            },
        )
    elif record.status == "cancelled":
        return JSONResponse(
            status_code=400,
            content={
                "operation_id": record.id,
                "status": record.status,
                "message": "Operation was cancelled.",
            },
        )
    else:
        return JSONResponse(
            status_code=202,
            content={
                "operation_id": record.id,
                "status": record.status,
                "message": "Operation is still running.",
            },
        )


@router.get("/events")
async def sse_events_route(request: Request) -> StreamingResponse:
    """Server-Sent Events (SSE) stream of all operations events with resume support."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)

    last_event_id_str = request.headers.get("Last-Event-ID") or request.query_params.get(
        "last_event_id"
    )
    last_event_id = None
    if last_event_id_str:
        try:
            last_event_id = int(last_event_id_str)
        except ValueError:
            pass

    shutdown_event = cast(asyncio.Event, request.app.state.shutdown_event)

    async def event_generator() -> AsyncIterator[str]:
        yield "retry: 5000\n\n"

        if last_event_id is not None:
            hist_events = registry.list_operation_events(last_event_id=last_event_id)
            for event in hist_events:
                yield f"id: {event.id}\nevent: {event.event_type}\ndata: {event.data_json}\n\n"

        queue: asyncio.Queue[tuple[int, str, dict[str, Any]]] = asyncio.Queue()
        if not hasattr(request.app.state, "sse_listeners"):
            request.app.state.sse_listeners = []
        request.app.state.sse_listeners.append(queue)

        try:
            while not shutdown_event.is_set():
                if await request.is_disconnected():
                    break
                try:
                    ev_id, ev_type, ev_data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"id: {ev_id}\nevent: {ev_type}\ndata: {json.dumps(ev_data)}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            if (
                hasattr(request.app.state, "sse_listeners")
                and queue in request.app.state.sse_listeners
            ):
                request.app.state.sse_listeners.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/runs/{run_id}/lineage")
async def get_run_lineage(run_id: str) -> JSONResponse:
    """Fetch experiment lineage information for a run."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)
    record = registry.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    artifacts = registry.list_artifacts(run_id)
    exports = registry.list_exports(run_id)
    events = registry.list_run_events(run_id)

    return JSONResponse(
        {
            "run_id": record.id,
            "dataset_path": record.dataset_path,
            "dataset_fingerprint": record.dataset_fingerprint,
            "config_hash": record.config_hash,
            "code_version": record.code_version,
            "env_summary": (
                json.loads(cast(str, record.env_summary))
                if record.env_summary
                else None
            ),
            "parent_run_id": record.parent_run_id,
            "artifacts": [
                {
                    "id": a.id,
                    "type": a.type,
                    "path": a.path,
                    "sha256": a.sha256,
                    "size": a.size,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in artifacts
            ],
            "exports": [
                {
                    "id": e.id,
                    "source_checkpoint": e.source_checkpoint,
                    "artifact_path": e.artifact_path,
                    "format": e.format,
                    "duration_s": e.duration_s,
                    "validation_result": json.loads(cast(str, e.validation_result_json))
                    if e.validation_result_json
                    else None,
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in exports
            ],
            "events": [
                {
                    "id": ev.id,
                    "event_type": ev.event_type,
                    "from_status": ev.from_status,
                    "to_status": ev.to_status,
                    "message": ev.message,
                    "created_at": ev.created_at.isoformat() if ev.created_at else None,
                }
                for ev in events
            ],
        }
    )


@router.get("/runs/{run_id}/events")
async def get_run_events(run_id: str) -> JSONResponse:
    """Fetch all lifecycle and audit events for a single run."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)
    record = registry.get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    events = registry.list_run_events(run_id)
    return JSONResponse(
        [
            {
                "id": ev.id,
                "event_type": ev.event_type,
                "from_status": ev.from_status,
                "to_status": ev.to_status,
                "message": ev.message,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
                "extra": json.loads(cast(str, ev.extra_json)) if ev.extra_json else None,
            }
            for ev in events
        ]
    )


@router.get("/datasets")
async def list_datasets() -> JSONResponse:
    """List all registered datasets in the ledger."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)
    datasets = registry.list_datasets()
    return JSONResponse(
        [
            {
                "fingerprint": d.fingerprint,
                "path": d.path,
                "class_map": json.loads(cast(str, d.class_map_json)) if d.class_map_json else {},
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in datasets
        ]
    )


@router.get("/datasets/{fingerprint}")
async def get_dataset(fingerprint: str) -> JSONResponse:
    """Fetch single dataset record by fingerprint."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)
    d = registry.get_dataset(fingerprint)
    if d is None:
        raise HTTPException(status_code=404, detail=f"Dataset {fingerprint} not found.")
    return JSONResponse(
        {
            "fingerprint": d.fingerprint,
            "path": d.path,
            "class_map": json.loads(cast(str, d.class_map_json)) if d.class_map_json else {},
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
    )


@router.get("/exports")
async def list_exports() -> JSONResponse:
    """List all model exports recorded in the ledger."""
    from fovux.core.paths import ensure_fovux_dirs
    from fovux.core.runs import get_registry

    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)
    exports = registry.list_exports()
    return JSONResponse(
        [
            {
                "id": e.id,
                "run_id": e.run_id,
                "source_checkpoint": e.source_checkpoint,
                "artifact_path": e.artifact_path,
                "format": e.format,
                "duration_s": e.duration_s,
                "validation_result": json.loads(cast(str, e.validation_result_json))
                if e.validation_result_json
                else None,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in exports
        ]
    )
