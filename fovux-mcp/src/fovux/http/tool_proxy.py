"""HTTP-safe proxy registry for invoking Fovux tools locally."""

from __future__ import annotations

import hashlib
import json
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fovux.core.auth import Scope
from fovux.core.errors import FovuxError
from fovux.core.tool_registry import available_tools as registry_available_tools
from fovux.core.tool_registry import resolve_tool

_TOOL_CATEGORY_MIN_SCOPE: dict[str, set[Scope]] = {
    "read_only": {Scope.READ},
    "mutating": {Scope.DATASET_WRITE, Scope.RUN_START, Scope.EXPORT_WRITE},
    "long_running": {Scope.RUN_START},
    "destructive": {Scope.DESTRUCTIVE, Scope.ADMIN},
}


class HttpToolPolicyError(FovuxError):
    """Raised when an HTTP tool call violates the local policy."""

    code = "FOVUX_HTTP_001"


class HttpScopeError(FovuxError):
    """Raised when the bearer token lacks the required scope for a tool."""

    code = "FOVUX_HTTP_004"


@dataclass(frozen=True)
class HttpToolPolicy:
    """HTTP exposure policy for a local MCP tool."""

    category: str
    timeout_seconds: float
    concurrency_limit: int
    requires_confirmation: bool = False
    enabled: bool = True
    required_scope: Scope = Scope.READ


_S = Scope

HTTP_TOOL_POLICIES: dict[str, HttpToolPolicy] = {
    "active_learning_queue_list": HttpToolPolicy("read_only", 20.0, 2, required_scope=_S.READ),
    "active_learning_queue_rank": HttpToolPolicy(
        "mutating", 60.0, 1, True, required_scope=_S.RUN_START
    ),
    "active_learning_queue_submit": HttpToolPolicy(
        "mutating", 30.0, 1, True, required_scope=_S.DATASET_WRITE
    ),
    "active_learning_select": HttpToolPolicy(
        "mutating", 30.0, 1, True, required_scope=_S.RUN_START
    ),
    "annotation_quality_check": HttpToolPolicy("read_only", 20.0, 2, required_scope=_S.READ),
    "benchmark_latency": HttpToolPolicy("long_running", 60.0, 1, True, required_scope=_S.RUN_START),
    "dataset_augment": HttpToolPolicy("mutating", 60.0, 1, True, required_scope=_S.DATASET_WRITE),
    "dataset_convert": HttpToolPolicy("mutating", 60.0, 1, True, required_scope=_S.DATASET_WRITE),
    "dataset_find_duplicates": HttpToolPolicy("read_only", 30.0, 1, required_scope=_S.READ),
    "dataset_inspect": HttpToolPolicy("read_only", 20.0, 2, required_scope=_S.READ),
    "dataset_split": HttpToolPolicy("mutating", 60.0, 1, True, required_scope=_S.DATASET_WRITE),
    "dataset_validate": HttpToolPolicy("read_only", 30.0, 2, required_scope=_S.READ),
    "demo_init": HttpToolPolicy("mutating", 30.0, 1, True, required_scope=_S.DATASET_WRITE),
    "deployment_advise": HttpToolPolicy("mutating", 60.0, 1, True, required_scope=_S.EXPORT_WRITE),
    "distill_model": HttpToolPolicy("long_running", 120.0, 1, True, required_scope=_S.RUN_START),
    "eval_compare": HttpToolPolicy("read_only", 20.0, 2, required_scope=_S.READ),
    "eval_error_analysis": HttpToolPolicy("read_only", 30.0, 1, required_scope=_S.READ),
    "eval_per_class": HttpToolPolicy("read_only", 30.0, 1, required_scope=_S.READ),
    "eval_run": HttpToolPolicy("long_running", 120.0, 1, True, required_scope=_S.RUN_START),
    "export_reproducibility_bundle": HttpToolPolicy("read_only", 30.0, 2, required_scope=_S.READ),
    "export_onnx": HttpToolPolicy("mutating", 120.0, 1, True, required_scope=_S.EXPORT_WRITE),
    "export_tflite": HttpToolPolicy("mutating", 120.0, 1, True, required_scope=_S.EXPORT_WRITE),
    "fovux_doctor": HttpToolPolicy("read_only", 20.0, 2, required_scope=_S.READ),
    "generate_support_bundle": HttpToolPolicy("read_only", 30.0, 2, required_scope=_S.READ),
    "get_policy_status": HttpToolPolicy("read_only", 10.0, 4, required_scope=_S.READ),
    "infer_batch": HttpToolPolicy("mutating", 120.0, 1, True, required_scope=_S.RUN_START),
    "infer_ensemble": HttpToolPolicy("read_only", 60.0, 1, required_scope=_S.READ),
    "infer_image": HttpToolPolicy("read_only", 60.0, 2, required_scope=_S.READ),
    "infer_rtsp": HttpToolPolicy("long_running", 120.0, 1, True, required_scope=_S.RUN_START),
    "list_audit_events": HttpToolPolicy("read_only", 30.0, 2, required_scope=_S.READ),
    "model_compare_visual": HttpToolPolicy("read_only", 30.0, 2, required_scope=_S.READ),
    "model_list": HttpToolPolicy("read_only", 20.0, 4, required_scope=_S.READ),
    "model_profile": HttpToolPolicy("read_only", 30.0, 2, required_scope=_S.READ),
    "quantize_int8": HttpToolPolicy("mutating", 120.0, 1, True, required_scope=_S.DATASET_WRITE),
    "quantize_report": HttpToolPolicy("read_only", 30.0, 2, required_scope=_S.READ),
    "run_archive": HttpToolPolicy("destructive", 60.0, 1, True, required_scope=_S.DESTRUCTIVE),
    "run_compare": HttpToolPolicy("mutating", 30.0, 1, True, required_scope=_S.RUN_START),
    "run_delete": HttpToolPolicy("destructive", 30.0, 1, True, required_scope=_S.DESTRUCTIVE),
    "run_tag": HttpToolPolicy("mutating", 20.0, 2, True, required_scope=_S.RUN_START),
    "set_policy_mode": HttpToolPolicy("mutating", 10.0, 1, True, required_scope=_S.ADMIN),
    "sync_to_mlflow": HttpToolPolicy("mutating", 60.0, 1, True, required_scope=_S.EXPORT_WRITE),
    "train_adjust": HttpToolPolicy("mutating", 30.0, 1, True, required_scope=_S.RUN_START),
    "train_preflight": HttpToolPolicy("read_only", 30.0, 2, required_scope=_S.READ),
    "train_resume": HttpToolPolicy("mutating", 60.0, 1, True, required_scope=_S.RUN_START),
    "train_start": HttpToolPolicy("long_running", 60.0, 1, True, required_scope=_S.RUN_START),
    "train_status": HttpToolPolicy("read_only", 20.0, 4, required_scope=_S.READ),
    "train_stop": HttpToolPolicy("mutating", 30.0, 1, True, required_scope=_S.RUN_START),
}

del _S


def check_scope(policy: HttpToolPolicy, scopes: set[Scope]) -> None:
    """Check that the provided scopes satisfy the tool policy requirement."""
    from fovux.config import load_config

    config = load_config()
    policy_mode = getattr(config, "policy_mode", "developer").lower()

    # Bypasses scope check completely in lab mode
    if policy_mode == "lab":
        return

    if policy.required_scope not in scopes:
        raise HttpScopeError(
            f"Token lacks required scope '{policy.required_scope.value}' for tool.",
            hint=(
                f"Tool '{policy.category}' operations require {policy.required_scope.value} scope. "
                "Use a session token with the required scope or rotate to a full-access token."
            ),
        )


def available_tools() -> list[str]:
    """Return the tool names reachable through the HTTP proxy under the current policy mode."""
    from fovux.config import load_config

    config = load_config()
    policy_mode = getattr(config, "policy_mode", "developer").lower()

    registered = set(registry_available_tools())
    allowed = []
    for name, policy in HTTP_TOOL_POLICIES.items():
        if not policy.enabled or name not in registered:
            continue
        if policy_mode == "safe" and policy.category == "destructive":
            continue
        allowed.append(name)
    return sorted(allowed)


def policy_for_tool(name: str) -> HttpToolPolicy:
    """Return the HTTP policy for a reachable tool, adjusted by policy mode."""
    from fovux.config import load_config

    config = load_config()
    policy_mode = getattr(config, "policy_mode", "developer").lower()

    policy = HTTP_TOOL_POLICIES.get(name)
    if policy is None or not policy.enabled or name not in registry_available_tools():
        raise HttpToolPolicyError(
            f"Tool '{name}' is not available over HTTP.",
            hint="Use one of the enabled local HTTP tools exposed by this server.",
        )

    # Apply safe mode restrictions
    if policy_mode == "safe":
        if policy.category == "destructive":
            raise HttpToolPolicyError(
                f"Tool '{name}' is disabled in safe mode.",
                hint="Switch the policy mode to developer or lab to execute destructive tools.",
            )

    # Apply confirmation overrides based on policy mode
    requires_conf = policy.requires_confirmation
    if policy_mode == "safe" and policy.category in ("mutating", "long_running", "destructive"):
        requires_conf = True
    elif policy_mode in ("automation", "lab"):
        requires_conf = False

    return HttpToolPolicy(
        category=policy.category,
        timeout_seconds=policy.timeout_seconds,
        concurrency_limit=policy.concurrency_limit,
        requires_confirmation=requires_conf,
        enabled=policy.enabled,
        required_scope=policy.required_scope,
    )


def payload_hash(payload: Mapping[str, object]) -> str:
    """Return a redacted deterministic hash for audit logging."""
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def invoke_tool(name: str, payload: Mapping[str, object]) -> dict[str, Any]:
    """Invoke a local tool by name using a JSON-compatible payload."""
    policy_for_tool(name)

    if "confirm" in payload:
        warnings.warn(
            "The 'confirm' field is deprecated. Use the challenge flow instead: "
            "POST /tools/{name}/challenge",
            DeprecationWarning,
            stacklevel=2,
        )

    tool = resolve_tool(name)

    kwargs = {
        str(key): value
        for key, value in payload.items()
        if str(key) not in ("confirm", "challenge_id")
    }
    try:
        return tool(**kwargs)
    except FovuxError:
        raise
