"""HTTP-safe proxy registry for invoking Fovux tools locally."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fovux.core.errors import FovuxError
from fovux.core.tool_registry import available_tools as registry_available_tools
from fovux.core.tool_registry import resolve_tool


class HttpToolPolicyError(FovuxError):
    """Raised when an HTTP tool call violates the local policy."""

    code = "FOVUX_HTTP_001"


@dataclass(frozen=True)
class HttpToolPolicy:
    """HTTP exposure policy for a local MCP tool."""

    category: str
    timeout_seconds: float
    concurrency_limit: int
    requires_confirmation: bool = False
    enabled: bool = True


HTTP_TOOL_POLICIES: dict[str, HttpToolPolicy] = {
    "active_learning_select": HttpToolPolicy("mutating", 30.0, 1, True),
    "annotation_quality_check": HttpToolPolicy("read_only", 20.0, 2),
    "benchmark_latency": HttpToolPolicy("long_running", 60.0, 1, True),
    "dataset_augment": HttpToolPolicy("mutating", 60.0, 1, True),
    "dataset_convert": HttpToolPolicy("mutating", 60.0, 1, True),
    "dataset_find_duplicates": HttpToolPolicy("read_only", 30.0, 1),
    "dataset_inspect": HttpToolPolicy("read_only", 20.0, 2),
    "dataset_split": HttpToolPolicy("mutating", 60.0, 1, True),
    "dataset_validate": HttpToolPolicy("read_only", 30.0, 2),
    "distill_model": HttpToolPolicy("long_running", 120.0, 1, True),
    "eval_compare": HttpToolPolicy("read_only", 20.0, 2),
    "eval_error_analysis": HttpToolPolicy("read_only", 30.0, 1),
    "eval_per_class": HttpToolPolicy("read_only", 30.0, 1),
    "eval_run": HttpToolPolicy("long_running", 120.0, 1, True),
    "export_onnx": HttpToolPolicy("mutating", 120.0, 1, True),
    "export_tflite": HttpToolPolicy("mutating", 120.0, 1, True),
    "fovux_doctor": HttpToolPolicy("read_only", 20.0, 2),
    "infer_batch": HttpToolPolicy("mutating", 120.0, 1, True),
    "infer_ensemble": HttpToolPolicy("read_only", 60.0, 1),
    "infer_image": HttpToolPolicy("read_only", 60.0, 2),
    "infer_rtsp": HttpToolPolicy("long_running", 120.0, 1, True),
    "model_compare_visual": HttpToolPolicy("read_only", 30.0, 2),
    "model_list": HttpToolPolicy("read_only", 20.0, 4),
    "model_profile": HttpToolPolicy("read_only", 30.0, 2),
    "quantize_int8": HttpToolPolicy("mutating", 120.0, 1, True),
    "quantize_report": HttpToolPolicy("read_only", 30.0, 2),
    "run_archive": HttpToolPolicy("destructive", 60.0, 1, True),
    "run_compare": HttpToolPolicy("mutating", 30.0, 1, True),
    "run_delete": HttpToolPolicy("destructive", 30.0, 1, True),
    "run_tag": HttpToolPolicy("mutating", 20.0, 2, True),
    "sync_to_mlflow": HttpToolPolicy("mutating", 60.0, 1, True),
    "train_adjust": HttpToolPolicy("mutating", 30.0, 1, True),
    "train_resume": HttpToolPolicy("mutating", 60.0, 1, True),
    "train_start": HttpToolPolicy("long_running", 60.0, 1, True),
    "train_status": HttpToolPolicy("read_only", 20.0, 4),
    "train_stop": HttpToolPolicy("mutating", 30.0, 1, True),
}


def available_tools() -> list[str]:
    """Return the tool names reachable through the HTTP proxy."""
    registered = set(registry_available_tools())
    return sorted(
        name for name, policy in HTTP_TOOL_POLICIES.items() if policy.enabled and name in registered
    )


def policy_for_tool(name: str) -> HttpToolPolicy:
    """Return the HTTP policy for a reachable tool."""
    policy = HTTP_TOOL_POLICIES.get(name)
    if policy is None or not policy.enabled or name not in registry_available_tools():
        raise HttpToolPolicyError(
            f"Tool '{name}' is not available over HTTP.",
            hint="Use one of the enabled local HTTP tools exposed by this server.",
        )
    return policy


def payload_hash(payload: Mapping[str, object]) -> str:
    """Return a redacted deterministic hash for audit logging."""
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def invoke_tool(name: str, payload: Mapping[str, object]) -> dict[str, Any]:
    """Invoke a local tool by name using a JSON-compatible payload."""
    policy = policy_for_tool(name)
    confirmed = payload.get("confirm") is True
    if policy.requires_confirmation and not confirmed:
        raise HttpToolPolicyError(
            f"Tool '{name}' requires explicit HTTP confirmation.",
            hint="Pass confirm=true from a trusted local UI action.",
        )
    tool = resolve_tool(name)

    kwargs = {str(key): value for key, value in payload.items() if str(key) != "confirm"}
    try:
        return tool(**kwargs)
    except FovuxError:
        raise
