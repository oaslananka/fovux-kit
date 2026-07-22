"""Service-level tests for persistent background operations."""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any

import pytest

from fovux.core.auth import ALL_SCOPES
from fovux.core.runs import RunRegistry
from fovux.http.services.operations import (
    CreateOperationCommand,
    OperationRuntimeState,
    OperationService,
)
from fovux.http.services.tool_runtime import ToolRuntimeState
from fovux.http.tool_proxy import HTTP_TOOL_POLICIES


def _service(
    tmp_path: Path,
    registry: RunRegistry,
    invoker,
) -> OperationService:
    return OperationService(
        registry_provider=lambda: registry,
        home_provider=lambda: tmp_path,
        invoker=invoker,
        id_factory=lambda: "op_fixed",
    )


def _operation_events(registry: RunRegistry, operation_id: str) -> list[tuple[int, dict[str, Any]]]:
    return [
        (int(event.id), json.loads(str(event.data_json)))
        for event in registry.list_operation_events()
        if event.operation_id == operation_id
    ]


@pytest.mark.asyncio
async def test_operation_service_persists_success_and_idempotency(tmp_path: Path) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    calls: list[tuple[str, dict[str, Any]]] = []

    def invoke(name: str, payload: dict[str, Any]) -> dict[str, Any]:
        calls.append((name, payload))
        print("operation-output")
        return {"models": ["a"]}

    service = _service(tmp_path, registry, invoke)
    runtime = OperationRuntimeState()
    queue: asyncio.Queue[tuple[int, str, dict[str, Any]]] = asyncio.Queue()
    runtime.sse_listeners.append(queue)
    tools = ToolRuntimeState.from_policies({"model_list": HTTP_TOOL_POLICIES["model_list"]})
    command = CreateOperationCommand(
        tool="model_list",
        arguments={},
        idempotency_key="same-request",
    )

    created = service.create(runtime, tools, ALL_SCOPES, command)
    await asyncio.gather(*list(runtime.active_tasks.values()))
    existing = service.create(runtime, tools, ALL_SCOPES, command)
    record = registry.get_operation("op_fixed")
    events = _operation_events(registry, "op_fixed")
    notifications = []
    while not queue.empty():
        notifications.append(queue.get_nowait())

    assert created.status_code == 201
    assert existing.status_code == 200
    assert record is not None and record.status == "succeeded"
    assert calls == [("model_list", {})]
    assert "operation-output" in (tmp_path / "operations" / "op_fixed.log").read_text()
    assert service.result("op_fixed").payload == {"models": ["a"]}
    expected_payloads = [
        {
            "operation_id": "op_fixed",
            "event_type": "status_change",
            "data": {"status": "pending"},
        },
        {
            "operation_id": "op_fixed",
            "event_type": "status_change",
            "data": {"status": "running"},
        },
        {
            "operation_id": "op_fixed",
            "event_type": "status_change",
            "data": {"status": "succeeded", "result": {"models": ["a"]}, "run_id": None},
        },
    ]
    assert [payload for _event_id, payload in events] == expected_payloads
    assert [payload for _id, _type, payload in notifications] == expected_payloads
    assert [event_id for event_id, _type, _payload in notifications] == [
        event_id for event_id, _payload in events
    ]


@pytest.mark.asyncio
async def test_operation_service_persists_failure_without_http_client(tmp_path: Path) -> None:
    registry = RunRegistry(tmp_path / "runs.db")

    def fail(_name: str, _payload: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("boom")

    service = _service(tmp_path, registry, fail)
    runtime = OperationRuntimeState()
    tools = ToolRuntimeState.from_policies({"model_list": HTTP_TOOL_POLICIES["model_list"]})

    service.create(runtime, tools, ALL_SCOPES, CreateOperationCommand(tool="model_list"))
    await asyncio.gather(*list(runtime.active_tasks.values()))
    outcome = service.result("op_fixed")
    events = _operation_events(registry, "op_fixed")

    assert outcome.status_code == 500
    assert outcome.payload["error_type"] == "RuntimeError"
    assert outcome.payload["error"] == "boom"
    assert [payload["data"]["status"] for _event_id, payload in events] == [
        "pending",
        "running",
        "failed",
    ]
    assert all(payload["operation_id"] == "op_fixed" for _event_id, payload in events)


@pytest.mark.asyncio
async def test_operation_service_cancels_active_task_and_notifies_listener(tmp_path: Path) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    registry.create_operation(op_id="op_cancel", tool="model_list", arguments={})
    service = _service(tmp_path, registry, lambda _name, _payload: {})
    runtime = OperationRuntimeState()
    task = asyncio.create_task(asyncio.sleep(60))
    runtime.active_tasks["op_cancel"] = task
    queue: asyncio.Queue[tuple[int, str, dict[str, Any]]] = asyncio.Queue()
    runtime.sse_listeners.append(queue)

    outcome = service.cancel(runtime, "op_cancel")
    event_id, event_type, event_payload = await queue.get()
    await asyncio.gather(task, return_exceptions=True)
    events = _operation_events(registry, "op_cancel")

    assert outcome.status_code == 200
    assert outcome.payload["status"] == "cancelled"
    assert event_id > 0
    assert event_type == "status_change"
    assert event_payload["data"] == {"status": "cancelled"}
    assert [payload["data"]["status"] for _persisted_id, payload in events] == ["cancelled"]
    assert event_id == events[0][0]
    assert queue.empty()


@pytest.mark.asyncio
async def test_operation_service_cancel_race_records_one_terminal_event(tmp_path: Path) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    registry.create_operation(op_id="op_race", tool="model_list", arguments={})
    worker_started = threading.Event()
    worker_release = threading.Event()

    def block(_name: str, _payload: dict[str, Any]) -> dict[str, Any]:
        worker_started.set()
        worker_release.wait(timeout=5)
        return {}

    service = OperationService(
        registry_provider=lambda: registry,
        home_provider=lambda: tmp_path,
        invoker=block,
    )
    runtime = OperationRuntimeState()
    queue: asyncio.Queue[tuple[int, str, dict[str, Any]]] = asyncio.Queue()
    runtime.sse_listeners.append(queue)
    task = asyncio.create_task(
        service.run_in_background(
            runtime,
            operation_id="op_race",
            tool_name="model_list",
            payload={},
            semaphore=asyncio.Semaphore(1),
        )
    )
    runtime.active_tasks["op_race"] = task
    assert await asyncio.to_thread(worker_started.wait, 2) is True

    outcome = service.cancel(runtime, "op_race")
    worker_release.set()
    await asyncio.gather(task, return_exceptions=True)
    events = _operation_events(registry, "op_race")
    notifications = []
    while not queue.empty():
        notifications.append(queue.get_nowait())

    assert outcome.payload["status"] == "cancelled"
    assert [payload["data"]["status"] for _id, payload in events] == [
        "running",
        "cancelled",
    ]
    assert [payload["data"]["status"] for _id, _type, payload in notifications] == [
        "running",
        "cancelled",
    ]
    assert [event_id for event_id, _type, _payload in notifications] == [
        event_id for event_id, _payload in events
    ]


@pytest.mark.asyncio
async def test_operation_event_stream_replays_history_and_stops_on_disconnect(
    tmp_path: Path,
) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    registry.create_operation(op_id="op_events", tool="model_list", arguments={})
    event = registry.create_operation_event("op_events", "status_change", {"status": "pending"})
    service = _service(tmp_path, registry, lambda _name, _payload: {})
    runtime = OperationRuntimeState()
    disconnected = False

    async def is_disconnected() -> bool:
        nonlocal disconnected
        value = disconnected
        disconnected = True
        return value

    stream = service.event_stream(
        runtime,
        last_event_id=event.id - 1,
        disconnect_check=is_disconnected,
        shutdown_event=asyncio.Event(),
    )
    first = await anext(stream)
    replay = await anext(stream)
    await stream.aclose()

    assert first == "retry: 5000\n\n"
    assert f"id: {event.id}" in replay
    assert "event: status_change" in replay
    assert runtime.sse_listeners == []


@pytest.mark.asyncio
async def test_operation_event_stream_shutdown_does_not_create_events(tmp_path: Path) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    registry.create_operation(op_id="op_shutdown", tool="model_list", arguments={})
    event = registry.create_operation_event("op_shutdown", "status_change", {"status": "pending"})
    service = _service(tmp_path, registry, lambda _name, _payload: {})
    shutdown_event = asyncio.Event()
    shutdown_event.set()

    async def connected() -> bool:
        return False

    stream = service.event_stream(
        OperationRuntimeState(),
        last_event_id=event.id,
        disconnect_check=connected,
        shutdown_event=shutdown_event,
    )

    assert await anext(stream) == "retry: 5000\n\n"
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    assert _operation_events(registry, "op_shutdown") == [(int(event.id), {"status": "pending"})]
