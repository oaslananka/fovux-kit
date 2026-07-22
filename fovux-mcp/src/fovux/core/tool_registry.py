"""Central tool registry used by the MCP server and HTTP proxy."""

from __future__ import annotations

import importlib
import json
from collections.abc import Callable
from importlib.resources import files
from typing import TYPE_CHECKING, Any, Protocol, cast

from fovux.core.logging import get_logger
from fovux.startup import startup_checkpoint

if TYPE_CHECKING:
    from fastmcp.tools import FunctionTool

ToolCallable = Callable[..., dict[str, Any]]


class ToolServer(Protocol):
    """Minimal FastMCP registration surface used by the runtime manifest."""

    def add_tool(self, tool: FunctionTool) -> object:
        """Register one tool object."""


_TOOL_SPECS: dict[str, str] = {
    "active_learning_select": "fovux.tools.active_learning_select:active_learning_select",
    "active_learning_queue_rank": (
        "fovux.tools.active_learning_queue_rank:active_learning_queue_rank"
    ),
    "active_learning_queue_list": (
        "fovux.tools.active_learning_queue_list:active_learning_queue_list"
    ),
    "active_learning_queue_submit": (
        "fovux.tools.active_learning_queue_submit:active_learning_queue_submit"
    ),
    "annotation_quality_check": "fovux.tools.annotation_quality_check:annotation_quality_check",
    "benchmark_latency": "fovux.tools.benchmark_latency:benchmark_latency",
    "deployment_advise": "fovux.tools.deployment_advise:deployment_advise",
    "demo_init": "fovux.tools.demo_init:demo_init",
    "dataset_augment": "fovux.tools.dataset_augment:dataset_augment",
    "dataset_convert": "fovux.tools.dataset_convert:dataset_convert",
    "dataset_find_duplicates": "fovux.tools.dataset_find_duplicates:dataset_find_duplicates",
    "dataset_inspect": "fovux.tools.dataset_inspect:dataset_inspect",
    "dataset_split": "fovux.tools.dataset_split:dataset_split",
    "dataset_validate": "fovux.tools.dataset_validate:dataset_validate",
    "distill_model": "fovux.tools.distill_model:distill_model",
    "eval_compare": "fovux.tools.eval_compare:eval_compare",
    "eval_error_analysis": "fovux.tools.eval_error_analysis:eval_error_analysis",
    "eval_per_class": "fovux.tools.eval_per_class:eval_per_class",
    "eval_run": "fovux.tools.eval_run:eval_run",
    "export_onnx": "fovux.tools.export_onnx:export_onnx",
    "export_reproducibility_bundle": ("fovux.tools.bundles:export_reproducibility_bundle"),
    "export_tflite": "fovux.tools.export_tflite:export_tflite",
    "fovux_doctor": "fovux.tools.fovux_doctor:fovux_doctor",
    "generate_support_bundle": "fovux.tools.bundles:generate_support_bundle",
    "get_policy_status": "fovux.tools.bundles:get_policy_status",
    "infer_ensemble": "fovux.tools.infer_ensemble:infer_ensemble",
    "infer_batch": "fovux.tools.infer_batch:infer_batch",
    "infer_image": "fovux.tools.infer_image:infer_image",
    "infer_rtsp": "fovux.tools.infer_rtsp:infer_rtsp",
    "list_audit_events": "fovux.tools.bundles:list_audit_events",
    "model_compare_visual": "fovux.tools.model_compare_visual:model_compare_visual",
    "model_list": "fovux.tools.model_list:model_list",
    "model_profile": "fovux.tools.model_profile:model_profile",
    "quantize_int8": "fovux.tools.quantize_int8:quantize_int8",
    "quantize_report": "fovux.tools.quantize_report:quantize_report",
    "run_archive": "fovux.tools.run_archive:run_archive",
    "run_compare": "fovux.tools.run_compare:run_compare",
    "run_delete": "fovux.tools.run_delete:run_delete",
    "run_tag": "fovux.tools.run_tag:run_tag",
    "set_policy_mode": "fovux.tools.bundles:set_policy_mode",
    "sync_to_mlflow": "fovux.tools.sync_to_mlflow:sync_to_mlflow",
    "train_adjust": "fovux.tools.train_adjust:train_adjust",
    "train_preflight": "fovux.tools.train_preflight:train_preflight",
    "train_resume": "fovux.tools.train_resume:train_resume",
    "train_start": "fovux.tools.train_start:train_start",
    "train_status": "fovux.tools.train_status:train_status",
    "train_stop": "fovux.tools.train_stop:train_stop",
}


def _load_runtime_manifest() -> dict[str, Any]:
    """Load and validate the packaged schema manifest without importing implementations."""
    manifest_path = files("fovux").joinpath("tool_manifest.json")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise RuntimeError("Invalid Fovux runtime tool manifest.")
    tools = payload.get("tools")
    if not isinstance(tools, list) or len(tools) != len(_TOOL_SPECS):
        raise RuntimeError("Fovux runtime tool manifest does not match the registry.")
    names: list[str] = []
    for raw_record in tools:
        if not isinstance(raw_record, dict):
            raise RuntimeError("Fovux runtime tool manifest contains a non-object record.")
        name = raw_record.get("name")
        target = raw_record.get("callable")
        input_schema = raw_record.get("inputSchema")
        output_schema = raw_record.get("outputSchema")
        if not isinstance(name, str) or target != _TOOL_SPECS.get(name):
            raise RuntimeError(f"Runtime tool manifest target drifted for {name!r}.")
        if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
            raise RuntimeError(f"Runtime tool manifest input schema drifted for {name}.")
        if output_schema is not None and (
            not isinstance(output_schema, dict) or output_schema.get("type") != "object"
        ):
            raise RuntimeError(f"Runtime tool manifest output schema drifted for {name}.")
        names.append(name)
    if names != sorted(_TOOL_SPECS):
        raise RuntimeError("Fovux runtime tool manifest order or names drifted.")
    startup_checkpoint("tool_manifest_loaded", total_tools=len(names))
    return cast(dict[str, Any], payload)


def _lazy_tool_callable(name: str) -> Callable[..., Any]:
    """Return a proxy that imports and validates one implementation on first invocation."""

    async def invoke(**kwargs: object) -> object:
        from fastmcp.tools import FunctionTool

        implementation = FunctionTool.from_function(resolve_tool(name))
        return await implementation.run(cast(dict[str, Any], kwargs))

    invoke.__name__ = name
    invoke.__qualname__ = name
    return invoke


def register_manifest_tools(server: ToolServer) -> None:
    """Register schema-complete lazy tool proxies from the packaged manifest."""
    from fastmcp.tools import FunctionTool
    from mcp.types import ToolAnnotations

    manifest = _load_runtime_manifest()
    for record in cast(list[dict[str, Any]], manifest["tools"]):
        name = cast(str, record["name"])
        raw_annotations = record.get("annotations")
        annotations = (
            ToolAnnotations.model_validate(raw_annotations)
            if isinstance(raw_annotations, dict)
            else None
        )
        server.add_tool(
            FunctionTool(
                name=name,
                title=cast(str | None, record.get("title")),
                description=cast(str, record["description"]),
                parameters=cast(dict[str, Any], record["inputSchema"]),
                output_schema=cast(dict[str, Any] | None, record.get("outputSchema")),
                annotations=annotations,
                fn=_lazy_tool_callable(name),
            )
        )
    startup_checkpoint("lazy_tool_registration_complete", total_tools=len(_TOOL_SPECS))
    get_logger(__name__).info("tool_registry_loaded", total_tools=len(_TOOL_SPECS), lazy=True)


def register_all() -> None:
    """Import every tool module so FastMCP decorators register against the singleton."""
    for target in _TOOL_SPECS.values():
        module_name, _ = target.split(":", maxsplit=1)
        importlib.import_module(module_name)
    get_logger(__name__).info("tool_registry_loaded", total_tools=len(_TOOL_SPECS))


def available_tools() -> list[str]:
    """Return all HTTP-exposed tool names."""
    return sorted(_TOOL_SPECS)


def list_tool_names() -> list[str]:
    """Return all registered Fovux tool names in stable sorted order."""
    return available_tools()


def resolve_tool(name: str) -> ToolCallable:
    """Resolve a tool name to its callable."""
    target = _TOOL_SPECS.get(name)
    if target is None:
        raise KeyError(name)
    module_name, attr_name = target.split(":", maxsplit=1)
    module = importlib.import_module(module_name)
    return cast(ToolCallable, getattr(module, attr_name))
