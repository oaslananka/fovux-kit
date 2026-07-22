"""Service-level tests for tool challenges and invocation orchestration."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from fovux.http.services.errors import ServiceError
from fovux.http.services.tool_runtime import ToolRuntimeState
from fovux.http.services.tools import (
    ChallengeService,
    ToolInvocationContext,
    ToolInvocationService,
)
from fovux.http.tool_proxy import HTTP_TOOL_POLICIES, HttpToolPolicy


def _runtime(*names: str) -> ToolRuntimeState:
    policies = {name: HTTP_TOOL_POLICIES[name] for name in names}
    return ToolRuntimeState.from_policies(policies)


def test_challenge_service_rejects_read_only_and_binds_risky_payload() -> None:
    runtime = _runtime("model_list", "train_start")
    service = ChallengeService()

    with pytest.raises(ServiceError) as exc_info:
        service.request(runtime, "model_list", {})
    outcome = service.request(
        runtime,
        "train_start",
        {"dataset_path": "/datasets/project", "model": "yolo.pt"},
    )

    assert exc_info.value.status_code == 403
    assert outcome.status_code == 201
    assert outcome.payload["tool"] == "train_start"
    summary = outcome.payload["summary"]
    assert isinstance(summary, dict)
    assert summary["resolved_paths"] == ["/datasets/project"]
    assert summary["destructive_impact"] is False
    assert outcome.payload["challenge_id"] in runtime.challenges


@pytest.mark.asyncio
async def test_tool_service_invokes_with_exact_challenge_and_audit_context() -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    def invoke(name: str, payload: dict[str, object]) -> dict[str, Any]:
        calls.append((name, payload))
        return {"run_id": "run_1"}

    runtime = _runtime("train_start")
    challenge = ChallengeService()
    challenge_outcome = challenge.request(
        runtime, "train_start", {"dataset_path": "/datasets/project"}
    )
    challenge_id = str(challenge_outcome.payload["challenge_id"])
    service = ToolInvocationService(invoker=invoke)

    outcome = await service.invoke(
        runtime,
        ToolInvocationContext(actor="actor-fingerprint", origin="127.0.0.1"),
        "train_start",
        {"dataset_path": "/datasets/project", "challenge_id": challenge_id},
    )

    assert outcome.status_code == 200
    assert outcome.payload == {"run_id": "run_1"}
    assert calls == [
        ("train_start", {"dataset_path": "/datasets/project", "challenge_id": challenge_id})
    ]
    assert runtime.challenges[challenge_id].used is True


@pytest.mark.asyncio
async def test_tool_service_returns_running_and_completed_timeout_results() -> None:
    runtime = _runtime("model_list")
    service = ToolInvocationService(invoker=lambda _name, _payload: {"models": []})
    context = ToolInvocationContext(actor="actor", origin="local")
    key = service.operation_key("model_list", {})
    operation_id = service.operation_id("model_list", {})
    pending: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    runtime.operations[key] = pending

    running = await service.invoke(runtime, context, "model_list", {})
    pending.set_result({"models": ["late"]})
    runtime.operations.pop(key)
    runtime.operation_results[key] = {
        "operation_id": operation_id,
        "status": "succeeded",
        "result": {"models": ["late"]},
        "finished_at": service.now(),
    }
    completed = await service.invoke(runtime, context, "model_list", {})

    assert running.status_code == 202
    assert running.payload["status"] == "running"
    assert completed.status_code == 200
    assert completed.payload == {"models": ["late"]}


@pytest.mark.asyncio
async def test_tool_service_enforces_concurrency_limit() -> None:
    runtime = ToolRuntimeState.from_policies(
        {
            "model_list": HttpToolPolicy(
                category="read_only",
                timeout_seconds=5.0,
                concurrency_limit=1,
            )
        }
    )
    await runtime.semaphores["model_list"].acquire()
    service = ToolInvocationService(invoker=lambda _name, _payload: {})
    context = ToolInvocationContext(actor="actor", origin="local")

    with pytest.raises(ServiceError) as exc_info:
        await service.invoke(runtime, context, "model_list", {})

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail == "Tool concurrency limit exceeded."
