"""model_profile — lightweight checkpoint profiling for local model selection."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.schemas.diagnostics import ModelProfileInput, ModelProfileOutput
from fovux.server import mcp


@mcp.tool()
def model_profile(
    checkpoint: str,
    imgsz: int = 640,
    device: str = "auto",
) -> dict[str, Any]:
    """Profile a checkpoint for parameter count, GFLOPs, layers, and rough memory footprint."""
    inp = ModelProfileInput(checkpoint=checkpoint, imgsz=imgsz, device=device)
    with tool_event("model_profile", checkpoint=checkpoint, imgsz=imgsz, device=device):
        return _run_model_profile(inp).model_dump(mode="json")


def _run_model_profile(inp: ModelProfileInput) -> ModelProfileOutput:
    checkpoint = resolve_checkpoint(inp.checkpoint)
    model = load_yolo_model(checkpoint)
    raw_model = getattr(model, "model", None)

    parameters = 0
    gradients = 0
    layers = 0
    if raw_model is not None and hasattr(raw_model, "parameters"):
        params = list(raw_model.parameters())
        parameters = sum(int(parameter.numel()) for parameter in params)
        gradients = sum(int(parameter.numel()) for parameter in params if parameter.requires_grad)
        if hasattr(raw_model, "modules"):
            layers = sum(1 for _ in raw_model.modules())

    architecture = Path(str(checkpoint)).stem
    gflops = _extract_gflops(model, inp.imgsz)
    model_size_mb = checkpoint.stat().st_size / (1024 * 1024)
    inference_memory_mb = round(model_size_mb * 1.5, 2)

    return ModelProfileOutput(
        checkpoint=str(checkpoint),
        architecture=architecture,
        parameters_millions=round(parameters / 1_000_000, 3),
        gradients_millions=round(gradients / 1_000_000, 3),
        gflops=gflops,
        layers=layers,
        model_size_mb=round(model_size_mb, 3),
        inference_memory_mb=inference_memory_mb,
    )


def _extract_gflops(model: object, imgsz: int) -> float:
    info_method = getattr(model, "info", None)
    if not callable(info_method):
        return 0.0
    try:
        info = info_method(verbose=False, detailed=True, imgsz=imgsz)
    except TypeError:
        info = info_method(verbose=False)
    except Exception:
        return 0.0

    if isinstance(info, dict):
        for key in ("gflops", "GFLOPs", "flops"):
            value = info.get(key)
            if isinstance(value, (int, float)):
                return round(float(value), 3)

    if isinstance(info, (list, tuple)) and len(info) >= 4 and isinstance(info[3], (int, float)):
        return round(float(info[3]), 3)

    if isinstance(info, str):
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*GFLOPs", info, flags=re.IGNORECASE)
        if match:
            return round(float(match.group(1)), 3)

    return 0.0
