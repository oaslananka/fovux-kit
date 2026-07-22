"""Challenge and local tool invocation services independent of FastAPI."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, cast

from pydantic import ValidationError

from fovux.core.errors import FovuxError
from fovux.core.logging import get_logger
from fovux.http.challenge import create_challenge, prune_expired_challenges, verify_challenge
from fovux.http.services.errors import ServiceError
from fovux.http.services.tool_runtime import (
    ToolRuntimeState,
    pop_fresh_tool_operation_result,
    prune_tool_operation_results,
    remember_timed_out_tool_worker,
)
from fovux.http.tool_proxy import (
    HttpToolPolicy,
    HttpToolPolicyError,
    payload_hash,
    policy_for_tool,
)
from fovux.schemas.errors import ErrorDetail

ToolInvoker = Callable[[str, Mapping[str, object]], dict[str, Any]]


def default_tool_invoker(name: str, payload: Mapping[str, object]) -> dict[str, Any]:
    """Resolve the invoker lazily so test and plugin overrides remain observable."""
    from fovux.http import tool_proxy

    return tool_proxy.invoke_tool(name, payload)


@dataclass(frozen=True)
class ServiceOutcome:
    """A transport-neutral status and JSON-compatible payload."""

    status_code: int
    payload: dict[str, Any]


@dataclass(frozen=True)
class ToolInvocationContext:
    """Redacted actor and origin metadata used for tool audit events."""

    actor: str
    origin: str | None


class ChallengeService:
    """Create exact-payload confirmation challenges for risky tools."""

    def request(
        self,
        runtime: ToolRuntimeState,
        tool_name: str,
        payload: dict[str, object],
    ) -> ServiceOutcome:
        """Create and store a challenge or raise the existing policy detail."""
        try:
            policy = policy_for_tool(tool_name)
        except HttpToolPolicyError as exc:
            raise ServiceError(403, _error_detail(exc)) from exc
        if not policy.requires_confirmation:
            raise ServiceError(
                403,
                {
                    "code": "FOVUX_HTTP_003",
                    "message": f"Tool '{tool_name}' does not require a confirmation challenge.",
                    "hint": "Read-only tools can be called directly without a challenge.",
                },
            )

        prune_expired_challenges(runtime.challenges)
        args_hash = payload_hash(payload)
        effect_summary = _challenge_effects(tool_name, policy.category, payload)
        record = create_challenge(
            tool_name=tool_name,
            args_hash=args_hash,
            risk_level=policy.category,
            resolved_paths=cast(list[str], effect_summary["resolved_paths"]),
        )
        runtime.challenges[record.challenge_id] = record
        return ServiceOutcome(
            201,
            {
                "challenge_id": record.challenge_id,
                "tool": tool_name,
                "risk_level": policy.category,
                "summary": {
                    "name": tool_name,
                    "args_hash": args_hash,
                    "params": {
                        str(key): value
                        for key, value in payload.items()
                        if str(key) not in ("confirm", "challenge_id")
                    },
                    **effect_summary,
                },
                "expires_at": record.expires_at,
            },
        )


class ToolInvocationService:
    """Enforce policy and execute local tools with bounded concurrency."""

    def __init__(self, invoker: ToolInvoker | None = None) -> None:
        """Initialize with an injectable synchronous tool invoker."""
        self._invoker = invoker or default_tool_invoker

    def now(self) -> float:
        """Return the monotonic clock used by retained operation results."""
        return time.monotonic()

    def operation_id(self, tool_name: str, payload: Mapping[str, object]) -> str:
        """Return the stable operation identifier for an exact payload."""
        return f"{tool_name}-{payload_hash(payload)}"

    def operation_key(self, tool_name: str, payload: Mapping[str, object]) -> str:
        """Return the internal lookup key for an exact payload."""
        return f"{tool_name}:{payload_hash(payload)}"

    async def invoke(
        self,
        runtime: ToolRuntimeState,
        context: ToolInvocationContext,
        tool_name: str,
        payload: dict[str, object],
    ) -> ServiceOutcome:
        """Invoke a tool or return the state of its one retained background execution."""
        started = self.now()
        args_hash = payload_hash(payload)
        operation_id = f"{tool_name}-{args_hash}"
        operation_key = f"{tool_name}:{args_hash}"
        logger = get_logger(__name__)
        try:
            policy = policy_for_tool(tool_name)
            self._verify_confirmation(runtime, policy, tool_name, payload)
            completed = self._completed_outcome(runtime, operation_key, operation_id)
            if completed is not None:
                _audit(logger, context, tool_name, args_hash, started, completed)
                return completed
            running = runtime.operations.get(operation_key)
            if running is not None and not running.done():
                outcome = _running_outcome(operation_id, "Tool execution is still running.")
                _audit(logger, context, tool_name, args_hash, started, outcome)
                return outcome
            return await self._start_worker(
                runtime,
                context,
                policy,
                tool_name,
                payload,
                args_hash,
                operation_key,
                operation_id,
                started,
            )
        except ServiceError:
            raise
        except HttpToolPolicyError as exc:
            _audit_failure(logger, context, tool_name, args_hash, started, "policy")
            raise ServiceError(403, _error_detail(exc)) from exc
        except ValidationError as exc:
            _audit_failure(logger, context, tool_name, args_hash, started, "validation_error")
            detail = ErrorDetail(
                code="FOVUX_HTTP_002",
                message="Tool payload validation failed.",
                hint=str(exc),
            )
            raise ServiceError(422, detail.model_dump(mode="json")) from exc
        except FovuxError as exc:
            _audit_failure(logger, context, tool_name, args_hash, started, exc.code)
            raise ServiceError(400, _error_detail(exc)) from exc

    def _verify_confirmation(
        self,
        runtime: ToolRuntimeState,
        policy: HttpToolPolicy,
        tool_name: str,
        payload: dict[str, object],
    ) -> None:
        if not policy.requires_confirmation:
            return
        prune_expired_challenges(runtime.challenges)
        challenge_id = payload.get("challenge_id")
        if not isinstance(challenge_id, str) or not challenge_id.strip():
            raise HttpToolPolicyError(
                f"Tool '{tool_name}' requires a confirmation challenge.",
                hint=(
                    "Call POST /tools/{name}/challenge first, then include the "
                    "returned challenge_id in the tool payload."
                ),
            )
        challenge_payload = {key: value for key, value in payload.items() if key != "challenge_id"}
        verify_challenge(
            runtime.challenges,
            challenge_id=challenge_id,
            tool_name=tool_name,
            args_hash=payload_hash(challenge_payload),
        )

    def _completed_outcome(
        self,
        runtime: ToolRuntimeState,
        operation_key: str,
        operation_id: str,
    ) -> ServiceOutcome | None:
        prune_tool_operation_results(runtime.operation_results)
        completed = pop_fresh_tool_operation_result(runtime.operation_results, operation_key)
        if completed is None:
            return None
        if completed.get("status") == "succeeded":
            return ServiceOutcome(200, cast(dict[str, Any], completed.get("result") or {}))
        return ServiceOutcome(
            500,
            {
                "operation_id": completed.get("operation_id", operation_id),
                "status": completed.get("status", "failed"),
                "error_type": completed.get("error_type"),
                "error": completed.get("error"),
            },
        )

    async def _start_worker(
        self,
        runtime: ToolRuntimeState,
        context: ToolInvocationContext,
        policy: HttpToolPolicy,
        tool_name: str,
        payload: dict[str, object],
        args_hash: str,
        operation_key: str,
        operation_id: str,
        started: float,
    ) -> ServiceOutcome:
        logger = get_logger(__name__)
        semaphore = runtime.semaphores[tool_name]
        try:
            await asyncio.wait_for(semaphore.acquire(), timeout=0.01)
        except TimeoutError as exc:
            _audit_failure(logger, context, tool_name, args_hash, started, "concurrency_limit")
            raise ServiceError(429, "Tool concurrency limit exceeded.") from exc

        release_deferred = False
        try:
            worker = asyncio.create_task(asyncio.to_thread(self._invoker, tool_name, payload))
            try:
                result = await asyncio.wait_for(
                    asyncio.shield(worker), timeout=policy.timeout_seconds
                )
            except TimeoutError:
                runtime.operations[operation_key] = worker
                worker.add_done_callback(
                    remember_timed_out_tool_worker(
                        semaphore=semaphore,
                        operations=runtime.operations,
                        results=runtime.operation_results,
                        operation_key=operation_key,
                        operation_id=operation_id,
                    )
                )
                release_deferred = True
                outcome = _running_outcome(
                    operation_id,
                    "Tool execution exceeded the request timeout and continues once.",
                )
                _audit(logger, context, tool_name, args_hash, started, outcome)
                return outcome
        finally:
            if not release_deferred:
                semaphore.release()
        outcome = ServiceOutcome(200, result)
        _audit(logger, context, tool_name, args_hash, started, outcome)
        return outcome


def _payload_paths(payload: Mapping[str, object]) -> list[str]:
    return [
        value
        for key, value in payload.items()
        if isinstance(value, str)
        and value
        and any(
            part in str(key).lower()
            for part in ("path", "dir", "file", "checkpoint", "output", "destination")
        )
    ]


def _challenge_effects(
    tool_name: str,
    category: str,
    payload: Mapping[str, object],
) -> dict[str, object]:
    input_paths = [
        value
        for key, value in payload.items()
        if isinstance(value, str)
        and any(
            part in str(key).lower()
            for part in ("dataset", "model", "checkpoint", "source", "input")
        )
    ]
    output_paths = [
        value
        for key, value in payload.items()
        if isinstance(value, str)
        and any(part in str(key).lower() for part in ("output", "destination", "export", "target"))
    ]
    destructive = category == "destructive" or tool_name in {"run_delete", "run_archive"}
    return {
        "tool_name": tool_name,
        "risk_level": category,
        "input_paths": input_paths,
        "output_paths": output_paths,
        "resolved_paths": _payload_paths(payload),
        "destructive_impact": destructive,
        "irreversible_effects": destructive,
        "human_prompt": f"Approve {tool_name} ({category}) after reviewing paths and impact flags.",
    }


def _running_outcome(operation_id: str, message: str) -> ServiceOutcome:
    return ServiceOutcome(
        202,
        {"operation_id": operation_id, "status": "running", "message": message},
    )


def _error_detail(error: FovuxError) -> dict[str, object]:
    return ErrorDetail(code=error.code, message=error.message, hint=error.hint).model_dump(
        mode="json"
    )


def _audit(
    logger: Any,  # noqa: ANN401
    context: ToolInvocationContext,
    tool_name: str,
    args_hash: str,
    started: float,
    outcome: ServiceOutcome,
) -> None:
    status = "success" if outcome.status_code == 200 else "accepted"
    failure_class = None if outcome.status_code < 500 else "background_operation_failed"
    method = logger.info if outcome.status_code < 500 else logger.warning
    method(
        "http_tool_audit",
        actor=context.actor,
        origin=context.origin,
        tool=tool_name,
        args_hash=args_hash,
        status=status if outcome.status_code < 500 else "failed",
        duration_ms=int((time.monotonic() - started) * 1000),
        failure_class=failure_class,
    )


def _audit_failure(
    logger: Any,  # noqa: ANN401
    context: ToolInvocationContext,
    tool_name: str,
    args_hash: str,
    started: float,
    failure_class: str,
) -> None:
    logger.warning(
        "http_tool_audit",
        actor=context.actor,
        origin=context.origin,
        tool=tool_name,
        args_hash=args_hash,
        status="rejected" if failure_class in {"policy", "concurrency_limit"} else "failed",
        duration_ms=int((time.monotonic() - started) * 1000),
        failure_class=failure_class,
    )
