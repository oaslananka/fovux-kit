"""export_onnx — export a YOLO checkpoint to ONNX with optional parity check."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, cast

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.errors import FovuxExportParityError
from fovux.core.export_history import record_export_history
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.core.validation import ensure_writable_output
from fovux.schemas.export import ExportOnnxInput, ExportOnnxOutput
from fovux.server import mcp


@mcp.tool()
def export_onnx(
    checkpoint: str,
    output_path: str | None = None,
    imgsz: int = 640,
    opset: int = 17,
    dynamic: bool = False,
    simplify: bool = True,
    half: bool = False,
    device: str = "auto",
    parity_check: bool = True,
    parity_tolerance: float = 1e-3,
) -> dict[str, Any]:
    """Export a YOLO .pt checkpoint to ONNX format with an optional roundtrip parity check."""
    inp = ExportOnnxInput(
        checkpoint=checkpoint,
        output_path=Path(output_path) if output_path else None,
        imgsz=imgsz,
        opset=opset,
        dynamic=dynamic,
        simplify=simplify,
        half=half,
        device=device,
        parity_check=parity_check,
        parity_tolerance=parity_tolerance,
    )
    with tool_event("export_onnx", checkpoint=checkpoint, output_path=output_path):
        return _run_export_onnx(inp).model_dump(mode="json")


def _run_export_onnx(inp: ExportOnnxInput) -> ExportOnnxOutput:
    ckpt_path = resolve_checkpoint(inp.checkpoint)

    t0 = time.perf_counter()
    onnx_path = _yolo_export_onnx(ckpt_path, inp)
    elapsed = time.perf_counter() - t0

    parity_passed: bool | None = None
    parity_max_diff: float | None = None

    if inp.parity_check:
        parity_passed, parity_max_diff = _check_parity(ckpt_path, onnx_path, inp)
        if not parity_passed:
            raise FovuxExportParityError(
                "ONNX parity check failed: "
                f"max_diff={parity_max_diff:.4e} > tol={inp.parity_tolerance:.4e}"
            )

    record_export_history(
        source_checkpoint=ckpt_path,
        artifact_path=onnx_path,
        format="onnx",
        duration_s=elapsed,
        metadata={
            "opset": inp.opset,
            "parity_passed": parity_passed,
            "parity_max_diff": parity_max_diff,
        },
    )

    return ExportOnnxOutput(
        checkpoint=str(ckpt_path),
        onnx_path=onnx_path,
        output_path=onnx_path,
        export_duration_seconds=elapsed,
        parity_passed=parity_passed,
        parity_max_diff=parity_max_diff,
        file_size_mb=(onnx_path.stat().st_size / (1024 * 1024)) if onnx_path.exists() else 0.0,
        opset=inp.opset,
        model_size_bytes=onnx_path.stat().st_size if onnx_path.exists() else 0,
    )


def _yolo_export_onnx(ckpt_path: Path, inp: ExportOnnxInput) -> Path:
    model = load_yolo_model(ckpt_path)
    export_path = model.export(
        format="onnx",
        imgsz=inp.imgsz,
        opset=inp.opset,
        dynamic=inp.dynamic,
        simplify=inp.simplify,
        half=inp.half,
        device=inp.device,
        nms=inp.nms,
    )
    result_path = Path(str(export_path))
    if inp.output_path is not None and inp.output_path != result_path:
        target_path = ensure_writable_output(inp.output_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.rename(target_path)
        result_path = target_path
    return result_path


def _check_parity(
    pt_path: Path,
    onnx_path: Path,
    inp: ExportOnnxInput,
) -> tuple[bool, float]:
    import importlib

    import numpy as np

    try:
        ort: Any = importlib.import_module("onnxruntime")
        invalid_graph_error = getattr(ort, "InvalidGraph", RuntimeError)
        missing_file_error = getattr(ort, "NoSuchFile", FileNotFoundError)
        dummy = np.random.default_rng(0).random((1, 3, inp.imgsz, inp.imgsz), dtype=np.float32)
        pt_outputs = _forward_pytorch(pt_path, dummy)
        session = ort.InferenceSession(str(onnx_path))
        input_name = session.get_inputs()[0].name
        onnx_outputs = session.run(None, {input_name: dummy})
    except RuntimeError as exc:
        raise FovuxExportParityError(
            f"ONNX parity check could not be executed: {exc}",
            hint=(
                "Inspect the exported graph and ensure both ONNX Runtime and PyTorch can run "
                "the model."
            ),
        ) from exc
    except Exception as exc:
        if "invalid_graph_error" in locals() and isinstance(
            exc, (invalid_graph_error, missing_file_error)
        ):
            raise FovuxExportParityError(
                f"ONNX parity check could not be executed: {exc}",
                hint=(
                    "Inspect the exported graph and ensure both ONNX Runtime and PyTorch can run "
                    "the model."
                ),
            ) from exc
        raise

    if len(pt_outputs) != len(onnx_outputs):
        raise FovuxExportParityError(
            "ONNX parity check failed: model output count differs between PyTorch and ONNX Runtime."
        )

    max_diff = 0.0
    all_close = True
    for index, (pt_output, onnx_output) in enumerate(zip(pt_outputs, onnx_outputs, strict=True)):
        pt_array = np.asarray(pt_output, dtype=np.float32)
        onnx_array = np.asarray(onnx_output, dtype=np.float32)
        if pt_array.shape != onnx_array.shape:
            raise FovuxExportParityError(
                "ONNX parity check failed: "
                f"output {index} shape mismatch {pt_array.shape} != {onnx_array.shape}"
            )
        diff = float(np.max(np.abs(pt_array - onnx_array))) if pt_array.size else 0.0
        max_diff = max(max_diff, diff)
        if not np.allclose(
            pt_array,
            onnx_array,
            atol=inp.parity_tolerance,
            rtol=inp.parity_tolerance,
        ):
            all_close = False

    return all_close, max_diff


def _forward_pytorch(pt_path: Path, dummy: object) -> list[Any]:
    torch = cast(Any, _load_torch())
    pt_model = load_yolo_model(pt_path)
    raw_model = getattr(pt_model, "model", None)
    if raw_model is None:
        raise FovuxExportParityError(
            "PyTorch parity check could not access the raw Ultralytics model."
        )

    tensor = torch.from_numpy(dummy)
    raw_model.eval()
    with torch.no_grad():
        outputs = raw_model(tensor)
    return _flatten_outputs(outputs)


def _load_torch() -> object:
    import importlib

    try:
        return importlib.import_module("torch")
    except ImportError as exc:
        raise FovuxExportParityError(
            "PyTorch is not available for ONNX parity checking.",
            hint="Install the `yolo` extra to enable Ultralytics/PyTorch-backed parity checks.",
        ) from exc


def _flatten_outputs(outputs: object) -> list[Any]:
    if hasattr(outputs, "detach"):
        return [outputs.detach().cpu().numpy()]
    if isinstance(outputs, (list, tuple)):
        flattened: list[Any] = []
        for item in outputs:
            flattened.extend(_flatten_outputs(item))
        return flattened
    if isinstance(outputs, dict):
        flattened = []
        for value in outputs.values():
            flattened.extend(_flatten_outputs(value))
        return flattened
    return [outputs]
