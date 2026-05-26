"""Central tool registry used by the MCP server and HTTP proxy."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, cast

from fovux.core.logging import get_logger

ToolCallable = Callable[..., dict[str, Any]]

_TOOL_SPECS: dict[str, str] = {
    "active_learning_select": "fovux.tools.active_learning_select:active_learning_select",
    "annotation_quality_check": "fovux.tools.annotation_quality_check:annotation_quality_check",
    "benchmark_latency": "fovux.tools.benchmark_latency:benchmark_latency",
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
    "export_tflite": "fovux.tools.export_tflite:export_tflite",
    "fovux_doctor": "fovux.tools.fovux_doctor:fovux_doctor",
    "infer_ensemble": "fovux.tools.infer_ensemble:infer_ensemble",
    "infer_batch": "fovux.tools.infer_batch:infer_batch",
    "infer_image": "fovux.tools.infer_image:infer_image",
    "infer_rtsp": "fovux.tools.infer_rtsp:infer_rtsp",
    "model_compare_visual": "fovux.tools.model_compare_visual:model_compare_visual",
    "model_list": "fovux.tools.model_list:model_list",
    "model_profile": "fovux.tools.model_profile:model_profile",
    "quantize_int8": "fovux.tools.quantize_int8:quantize_int8",
    "quantize_report": "fovux.tools.quantize_report:quantize_report",
    "run_archive": "fovux.tools.run_archive:run_archive",
    "run_compare": "fovux.tools.run_compare:run_compare",
    "run_delete": "fovux.tools.run_delete:run_delete",
    "run_tag": "fovux.tools.run_tag:run_tag",
    "sync_to_mlflow": "fovux.tools.sync_to_mlflow:sync_to_mlflow",
    "train_adjust": "fovux.tools.train_adjust:train_adjust",
    "train_resume": "fovux.tools.train_resume:train_resume",
    "train_start": "fovux.tools.train_start:train_start",
    "train_status": "fovux.tools.train_status:train_status",
    "train_stop": "fovux.tools.train_stop:train_stop",
}


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
