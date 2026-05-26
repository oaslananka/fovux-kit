"""quantize_int8 — INT8 post-training quantization via ONNX export."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.dataset_config import validate_yolo_data_yaml
from fovux.core.errors import FovuxDatasetEmptyError, FovuxDatasetNotFoundError
from fovux.core.export_history import record_export_history
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.core.validation import ensure_writable_output
from fovux.schemas.export import QuantizeInt8Input, QuantizeInt8Output
from fovux.server import mcp


@mcp.tool()
def quantize_int8(
    checkpoint: str,
    calibration_dataset: str,
    output_path: str | None = None,
    imgsz: int = 640,
    device: str = "auto",
) -> dict[str, Any]:
    """Produce an INT8-quantized ONNX model using a calibration dataset."""
    inp = QuantizeInt8Input(
        checkpoint=checkpoint,
        calibration_dataset=Path(calibration_dataset),
        output_path=Path(output_path) if output_path else None,
        imgsz=imgsz,
        device=device,
    )
    with tool_event(
        "quantize_int8",
        checkpoint=checkpoint,
        calibration_dataset=calibration_dataset,
    ):
        return _run_quantize_int8(inp).model_dump(mode="json")


def _run_quantize_int8(inp: QuantizeInt8Input) -> QuantizeInt8Output:
    calib_path = inp.calibration_dataset.expanduser().resolve()
    if not calib_path.exists():
        raise FovuxDatasetNotFoundError(str(calib_path))
    validate_yolo_data_yaml(calib_path)
    validate_calibration_dataset(calib_path)

    ckpt_path = resolve_checkpoint(inp.checkpoint)
    orig_size = ckpt_path.stat().st_size

    t0 = time.perf_counter()
    quantized_path = _yolo_quantize_int8(ckpt_path, calib_path, inp)
    elapsed = time.perf_counter() - t0

    quant_size = quantized_path.stat().st_size if quantized_path.exists() else 0
    reduction = ((orig_size - quant_size) / orig_size * 100) if orig_size > 0 else 0.0

    record_export_history(
        source_checkpoint=ckpt_path,
        artifact_path=quantized_path,
        format="onnx-int8",
        duration_s=elapsed,
        metadata={"imgsz": inp.imgsz, "size_reduction_pct": reduction},
    )

    return QuantizeInt8Output(
        checkpoint=str(ckpt_path),
        quantized_path=quantized_path,
        quantize_duration_seconds=elapsed,
        model_size_bytes=quant_size,
        size_reduction_pct=reduction,
    )


def validate_calibration_dataset(path: Path, min_images: int = 50) -> None:
    """Ensure INT8 calibration has enough image samples to be meaningful."""
    image_exts = {".jpg", ".jpeg", ".png", ".bmp"}
    image_count = sum(
        1 for item in path.rglob("*") if item.is_file() and item.suffix.lower() in image_exts
    )
    if image_count < min_images:
        raise FovuxDatasetEmptyError(
            str(path),
            message=(
                f"INT8 calibration requires at least {min_images} images; "
                f"found {image_count} in {path}."
            ),
        )


def _yolo_quantize_int8(
    ckpt_path: Path,
    calib_path: Path,
    inp: QuantizeInt8Input,
) -> Path:
    model = load_yolo_model(ckpt_path)
    export_path = model.export(
        format="onnx",
        imgsz=inp.imgsz,
        int8=True,
        data=str(calib_path / "data.yaml"),
        device=inp.device,
    )
    result_path = Path(str(export_path))
    if inp.output_path is not None and inp.output_path != result_path:
        target_path = ensure_writable_output(inp.output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.rename(target_path)
        result_path = target_path
    return result_path
