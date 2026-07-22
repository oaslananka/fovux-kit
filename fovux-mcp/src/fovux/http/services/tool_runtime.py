"""Runtime state and timeout-result helpers for HTTP tool invocation."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from fovux.core.logging import get_logger
from fovux.http.challenge import ChallengeRecord
from fovux.http.tool_proxy import HttpToolPolicy

TOOL_OPERATION_RESULT_TTL_SECONDS = 300.0
MAX_TOOL_OPERATION_RESULTS = 128


@dataclass
class ToolRuntimeState:
    """Mutable process-local state shared by challenge and tool services."""

    challenges: dict[str, ChallengeRecord] = field(default_factory=dict)
    semaphores: dict[str, asyncio.Semaphore] = field(default_factory=dict)
    operations: dict[str, asyncio.Future[Any]] = field(default_factory=dict)
    operation_results: dict[str, dict[str, object]] = field(default_factory=dict)

    @classmethod
    def from_policies(cls, policies: Mapping[str, HttpToolPolicy]) -> ToolRuntimeState:
        """Build runtime state with one semaphore per enabled policy."""
        return cls(
            semaphores={
                name: asyncio.Semaphore(policy.concurrency_limit)
                for name, policy in policies.items()
                if policy.enabled
            }
        )


def release_semaphore_after_worker(
    semaphore: asyncio.Semaphore,
) -> Callable[[asyncio.Future[Any]], None]:
    """Return a callback that reports worker failure and releases a semaphore."""
    logger = get_logger(__name__)

    def release(task: asyncio.Future[Any]) -> None:
        try:
            error = task.exception()
        except asyncio.CancelledError:
            error = None
        except Exception as exc:
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

    return release


def _completed_worker_result(
    task: asyncio.Future[Any],
    operation_id: str,
) -> tuple[dict[str, object], BaseException | None]:
    finished_at = time.monotonic()
    try:
        result = task.result()
    except asyncio.CancelledError:
        return {
            "operation_id": operation_id,
            "status": "cancelled",
            "finished_at": finished_at,
        }, None
    except Exception as exc:
        return {
            "operation_id": operation_id,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "finished_at": finished_at,
        }, exc
    return {
        "operation_id": operation_id,
        "status": "succeeded",
        "result": result,
        "finished_at": finished_at,
    }, None


def remember_timed_out_tool_worker(
    *,
    semaphore: asyncio.Semaphore,
    operations: dict[str, asyncio.Future[Any]],
    results: dict[str, dict[str, object]],
    operation_key: str,
    operation_id: str,
) -> Callable[[asyncio.Future[Any]], None]:
    """Persist a timed-out worker result and release its concurrency slot."""
    logger = get_logger(__name__)

    def complete(task: asyncio.Future[Any]) -> None:
        try:
            outcome, error = _completed_worker_result(task, operation_id)
            results[operation_key] = outcome
            if error is not None:
                logger.error(
                    "http_tool_worker_failed_after_timeout",
                    error_type=type(error).__name__,
                    error=str(error),
                )
        finally:
            operations.pop(operation_key, None)
            prune_tool_operation_results(results)
            semaphore.release()

    return complete


def pop_fresh_tool_operation_result(
    results: dict[str, dict[str, object]],
    operation_key: str,
) -> dict[str, object] | None:
    """Return a retained result when it is well-formed and not expired."""
    result = results.get(operation_key)
    if result is None:
        return None
    finished_at = result.get("finished_at")
    if not isinstance(finished_at, int | float):
        results.pop(operation_key, None)
        return None
    if time.monotonic() - float(finished_at) > TOOL_OPERATION_RESULT_TTL_SECONDS:
        results.pop(operation_key, None)
        return None
    return result


def prune_tool_operation_results(results: dict[str, dict[str, object]]) -> None:
    """Remove expired and excess retained background results."""
    now = time.monotonic()
    for key, result in list(results.items()):
        finished_at = result.get("finished_at")
        if not isinstance(finished_at, int | float):
            results.pop(key, None)
            continue
        if now - float(finished_at) > TOOL_OPERATION_RESULT_TTL_SECONDS:
            results.pop(key, None)
    if len(results) <= MAX_TOOL_OPERATION_RESULTS:
        return
    oldest = sorted(
        results.items(),
        key=lambda item: float(cast(int | float, item[1].get("finished_at", 0))),
    )
    for key, _result in oldest[: len(results) - MAX_TOOL_OPERATION_RESULTS]:
        results.pop(key, None)
