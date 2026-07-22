"""Persistent background operation orchestration independent of FastAPI."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from fovux.core.auth import Scope
from fovux.core.logging import get_logger
from fovux.core.runs import OperationRecord, RunRegistry
from fovux.http.challenge import prune_expired_challenges, verify_challenge
from fovux.http.services.errors import ServiceError
from fovux.http.services.tool_runtime import ToolRuntimeState
from fovux.http.services.tools import ServiceOutcome
from fovux.http.thread_stream import redirect_thread_output
from fovux.http.tool_proxy import check_scope, payload_hash, policy_for_tool

RegistryProvider = Callable[[], RunRegistry]
HomeProvider = Callable[[], Path]
ToolInvoker = Callable[[str, Mapping[str, object]], dict[str, Any]]


def default_operation_invoker(name: str, payload: Mapping[str, object]) -> dict[str, Any]:
    """Resolve the tool invoker lazily for runtime overrides and tests."""
    from fovux import server as _server
    from fovux.http import tool_proxy

    del _server
    return tool_proxy.invoke_tool(name, payload)


TrainStopper = Callable[[str], object]
DisconnectCheck = Callable[[], Awaitable[bool]]
OperationEvent = tuple[int, str, dict[str, Any]]


@dataclass(frozen=True)
class CreateOperationCommand:
    """Transport-neutral request to create a persistent operation."""

    tool: str
    arguments: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    challenge_id: str | None = None


@dataclass
class OperationRuntimeState:
    """Process-local task and SSE listener state."""

    active_tasks: dict[str, asyncio.Future[Any]] = field(default_factory=dict)
    sse_listeners: list[asyncio.Queue[OperationEvent]] = field(default_factory=list)


def default_registry_provider() -> RunRegistry:
    """Return the configured registry while preserving runtime overrides."""
    from fovux.core import paths as path_module
    from fovux.core import runs as runs_module

    paths = path_module.ensure_fovux_dirs()
    return runs_module.get_registry(paths.runs_db)


def default_home_provider() -> Path:
    """Return the configured Fovux home while preserving runtime overrides."""
    from fovux.core import paths as path_module

    return path_module.ensure_fovux_dirs().home


def default_train_stopper(run_id: str) -> object:
    """Stop a training run through the existing tool implementation."""
    from fovux.tools.train_stop import train_stop

    return train_stop(run_id=run_id)


class OperationService:
    """Create, execute, query, cancel, and stream persistent operations."""

    def __init__(
        self,
        *,
        registry_provider: RegistryProvider = default_registry_provider,
        home_provider: HomeProvider = default_home_provider,
        invoker: ToolInvoker | None = None,
        train_stopper: TrainStopper = default_train_stopper,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        """Initialize the service with injectable local dependencies."""
        self._registry_provider = registry_provider
        self._home_provider = home_provider
        self._invoker = invoker or default_operation_invoker
        self._train_stopper = train_stopper
        self._id_factory = id_factory or (lambda: f"op_{uuid.uuid4().hex[:12]}")

    def create(
        self,
        runtime: OperationRuntimeState,
        tools: ToolRuntimeState,
        scopes: set[Scope],
        command: CreateOperationCommand,
    ) -> ServiceOutcome:
        """Persist and schedule a background operation."""
        registry = self._registry_provider()
        policy = policy_for_tool(command.tool)
        check_scope(policy, scopes)
        self._verify_challenge(tools, command, policy.requires_confirmation)
        if command.idempotency_key:
            existing = registry.get_operation_by_idempotency_key(command.idempotency_key)
            if existing is not None:
                return ServiceOutcome(200, _operation_summary(existing))

        operation_id = self._id_factory()
        record = registry.create_operation(
            op_id=operation_id,
            tool=command.tool,
            arguments=command.arguments,
            idempotency_key=command.idempotency_key,
        )
        try:
            semaphore = tools.semaphores[command.tool]
        except KeyError as exc:
            raise ServiceError(403, f"Tool '{command.tool}' is not available over HTTP.") from exc
        task = asyncio.create_task(
            self.run_in_background(
                runtime,
                operation_id=operation_id,
                tool_name=command.tool,
                payload=command.arguments,
                semaphore=semaphore,
            )
        )
        runtime.active_tasks[operation_id] = task
        registry.create_operation_event(operation_id, "status_change", {"status": "pending"})
        return ServiceOutcome(201, _operation_summary(record))

    def get(self, operation_id: str) -> dict[str, Any]:
        """Return an operation summary or a typed 404."""
        record = self._registry_provider().get_operation(operation_id)
        if record is None:
            raise ServiceError(404, f"Operation {operation_id} not found.")
        return _operation_summary(record)

    def cancel(
        self,
        runtime: OperationRuntimeState,
        operation_id: str,
    ) -> ServiceOutcome:
        """Cancel an active operation and persist its terminal state."""
        registry = self._registry_provider()
        record = registry.get_operation(operation_id)
        if record is None:
            raise ServiceError(404, f"Operation {operation_id} not found.")
        if record.status in ("succeeded", "failed", "cancelled"):
            return ServiceOutcome(200, _operation_summary(record))

        task = runtime.active_tasks.get(operation_id)
        if task is not None:
            task.cancel()
        if record.run_id:
            try:
                self._train_stopper(str(record.run_id))
            except Exception as exc:
                get_logger(__name__).warning(
                    "http_operation_train_stop_failed",
                    operation_id=operation_id,
                    run_id=str(record.run_id),
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
        registry.update_operation_status(operation_id, "cancelled")
        registry.create_operation_event(operation_id, "status_change", {"status": "cancelled"})
        self._notify(runtime, operation_id, "status_change", {"status": "cancelled"})
        updated = registry.get_operation(operation_id)
        if updated is None:
            raise ServiceError(404, f"Operation {operation_id} not found.")
        return ServiceOutcome(200, _operation_summary(updated))

    def result(self, operation_id: str) -> ServiceOutcome:
        """Return the final result or current terminal/running representation."""
        record = self._registry_provider().get_operation(operation_id)
        if record is None:
            raise ServiceError(404, f"Operation {operation_id} not found.")
        if record.status == "succeeded":
            payload = json.loads(str(record.result_json)) if record.result_json else {}
            return ServiceOutcome(200, cast(dict[str, Any], payload))
        if record.status == "failed":
            return ServiceOutcome(
                500,
                {
                    "operation_id": record.id,
                    "status": record.status,
                    "error_type": record.error_type,
                    "error": record.error,
                },
            )
        if record.status == "cancelled":
            return ServiceOutcome(
                400,
                {
                    "operation_id": record.id,
                    "status": record.status,
                    "message": "Operation was cancelled.",
                },
            )
        return ServiceOutcome(
            202,
            {
                "operation_id": record.id,
                "status": record.status,
                "message": "Operation is still running.",
            },
        )

    async def run_in_background(
        self,
        runtime: OperationRuntimeState,
        *,
        operation_id: str,
        tool_name: str,
        payload: dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> None:
        """Execute one operation, persist transitions, and notify listeners."""
        registry = self._registry_provider()
        registry.update_operation_status(operation_id, "running")
        registry.create_operation_event(operation_id, "status_change", {"status": "running"})
        self._notify(runtime, operation_id, "status_change", {"status": "running"})
        log_file = self._operation_log_file(operation_id)
        await semaphore.acquire()

        def target() -> dict[str, Any]:
            with log_file.open("a", encoding="utf-8") as handle, redirect_thread_output(handle):
                handle.write(
                    f"--- Operation {operation_id} started at "
                    f"{time.strftime('%Y-%m-%d %H:%M:%S')} ---\n"
                )
                handle.flush()
                try:
                    return self._invoker(tool_name, payload)
                finally:
                    handle.write(f"--- Operation {operation_id} finished ---\n")
                    handle.flush()

        try:
            worker = asyncio.create_task(asyncio.to_thread(target))
            runtime.active_tasks[operation_id] = worker
            result = await worker
            run_id = str(result["run_id"]) if "run_id" in result else None
            registry.update_operation_status(
                operation_id, "succeeded", result=result, run_id=run_id
            )
            data = {"status": "succeeded", "result": result, "run_id": run_id}
            registry.create_operation_event(operation_id, "status_change", data)
            self._notify(runtime, operation_id, "status_change", data)
        except asyncio.CancelledError:
            registry.update_operation_status(operation_id, "cancelled")
            registry.create_operation_event(operation_id, "status_change", {"status": "cancelled"})
            self._notify(runtime, operation_id, "status_change", {"status": "cancelled"})
            raise
        except Exception as exc:
            data = {
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            registry.update_operation_status(
                operation_id,
                "failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            registry.create_operation_event(operation_id, "status_change", data)
            self._notify(runtime, operation_id, "status_change", data)
        finally:
            semaphore.release()
            runtime.active_tasks.pop(operation_id, None)

    async def log_stream(self, operation_id: str) -> AsyncIterator[str]:
        """Yield an operation or attached run log until the operation is terminal."""
        registry = self._registry_provider()
        record = registry.get_operation(operation_id)
        if record is None:
            raise ServiceError(404, f"Operation {operation_id} not found.")
        log_file = self._operation_log_file(operation_id)
        if record.run_id:
            run_log = self._home_provider() / "runs" / str(record.run_id) / "stdout.log"
            if run_log.exists():
                log_file = run_log
        for _ in range(20):
            if log_file.exists():
                break
            await asyncio.sleep(0.1)
        if not log_file.exists():
            yield "Log file not found.\n"
            return
        with log_file.open(encoding="utf-8", errors="replace") as handle:
            while True:
                line = handle.readline()
                if line:
                    yield line
                    continue
                current = registry.get_operation(operation_id)
                if current is None or current.status in ("succeeded", "failed", "cancelled"):
                    remaining = handle.read()
                    if remaining:
                        yield remaining
                    break
                await asyncio.sleep(0.5)

    async def event_stream(
        self,
        runtime: OperationRuntimeState,
        *,
        last_event_id: int | None,
        disconnect_check: DisconnectCheck,
        shutdown_event: asyncio.Event,
    ) -> AsyncIterator[str]:
        """Yield historical and live operation events in SSE format."""
        registry = self._registry_provider()
        yield "retry: 5000\n\n"
        if last_event_id is not None:
            for event in registry.list_operation_events(last_event_id=last_event_id):
                yield f"id: {event.id}\nevent: {event.event_type}\ndata: {event.data_json}\n\n"
        queue: asyncio.Queue[OperationEvent] = asyncio.Queue()
        runtime.sse_listeners.append(queue)
        try:
            while not shutdown_event.is_set():
                if await disconnect_check():
                    break
                try:
                    event_id, event_type, data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(data)}\n\n"
                except TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            if queue in runtime.sse_listeners:
                runtime.sse_listeners.remove(queue)

    def _verify_challenge(
        self,
        tools: ToolRuntimeState,
        command: CreateOperationCommand,
        requires_confirmation: bool,
    ) -> None:
        if not requires_confirmation:
            return
        prune_expired_challenges(tools.challenges)
        challenge_id = command.challenge_id or command.arguments.get("challenge_id")
        if not isinstance(challenge_id, str) or not challenge_id.strip():
            raise ServiceError(
                403,
                {
                    "code": "FOVUX_HTTP_001",
                    "message": f"Tool '{command.tool}' requires a confirmation challenge.",
                    "hint": (
                        "Call POST /tools/{name}/challenge first, then include the challenge_id."
                    ),
                },
            )
        verify_challenge(
            tools.challenges,
            challenge_id=challenge_id,
            tool_name=command.tool,
            args_hash=payload_hash(
                {key: value for key, value in command.arguments.items() if key != "challenge_id"}
            ),
        )

    def _notify(
        self,
        runtime: OperationRuntimeState,
        operation_id: str,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        payload = {"operation_id": operation_id, "event_type": event_type, "data": data}
        event = self._registry_provider().create_operation_event(operation_id, event_type, payload)
        for queue in list(runtime.sse_listeners):
            try:
                queue.put_nowait((cast(int, event.id), event_type, payload))
            except Exception as exc:
                get_logger(__name__).debug(
                    "http_operation_listener_notify_failed",
                    operation_id=operation_id,
                    error_type=type(exc).__name__,
                    error=str(exc),
                )

    def _operation_log_file(self, operation_id: str) -> Path:
        log_dir = self._home_provider() / "operations"
        log_dir.mkdir(parents=True, exist_ok=True)
        return log_dir / f"{operation_id}.log"


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
