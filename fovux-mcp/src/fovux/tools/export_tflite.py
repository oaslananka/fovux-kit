"""export_tflite — export a YOLO checkpoint to TFLite format."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.export_history import record_export_history
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.core.validation import ensure_writable_output
from fovux.schemas.export import ExportTfliteInput, ExportTfliteOutput
from fovux.server import mcp


@mcp.tool()
def export_tflite(
    checkpoint: str,
    output_path: str | None = None,
    imgsz: int = 640,
    half: bool = False,
    int8: bool = False,
    device: str = "auto",
) -> dict[str, Any]:
    """Export a YOLO .pt checkpoint to TFLite format."""
    inp = ExportTfliteInput(
        checkpoint=checkpoint,
        output_path=Path(output_path) if output_path else None,
        imgsz=imgsz,
        half=half,
        int8=int8,
        device=device,
    )
    with tool_event("export_tflite", checkpoint=checkpoint, output_path=output_path):
        return _run_export_tflite(inp).model_dump(mode="json")


def _run_export_tflite(inp: ExportTfliteInput) -> ExportTfliteOutput:
    ckpt_path = resolve_checkpoint(inp.checkpoint)

    t0 = time.perf_counter()
    tflite_path = _yolo_export_tflite(ckpt_path, inp)
    elapsed = time.perf_counter() - t0

    record_export_history(
        source_checkpoint=ckpt_path,
        artifact_path=tflite_path,
        format="tflite",
        duration_s=elapsed,
        metadata={"half": inp.half, "int8": inp.int8},
    )

    return ExportTfliteOutput(
        checkpoint=str(ckpt_path),
        tflite_path=tflite_path,
        output_path=tflite_path,
        export_duration_seconds=elapsed,
        file_size_mb=(tflite_path.stat().st_size / (1024 * 1024)) if tflite_path.exists() else 0.0,
        model_size_bytes=tflite_path.stat().st_size if tflite_path.exists() else 0,
    )


def _yolo_export_tflite(ckpt_path: Path, inp: ExportTfliteInput) -> Path:
    model = load_yolo_model(ckpt_path)
    export_path = model.export(
        format="tflite",
        imgsz=inp.imgsz,
        half=inp.half,
        int8=inp.int8,
        device=inp.device,
    )
    result_path = Path(str(export_path))
    if inp.output_path is not None and inp.output_path != result_path:
        target_path = ensure_writable_output(inp.output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.rename(target_path)
        result_path = target_path
    return result_path
