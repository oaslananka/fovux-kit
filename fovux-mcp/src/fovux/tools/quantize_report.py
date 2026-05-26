"""quantize_report — compare original vs quantized model accuracy and size."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.errors import FovuxExportParityError
from fovux.core.tooling import tool_event
from fovux.schemas.eval import EvalRunInput
from fovux.schemas.export import QuantizeReportInput, QuantizeReportOutput
from fovux.server import mcp
from fovux.tools.eval_run import _run_eval


@mcp.tool()
def quantize_report(
    original_checkpoint: str,
    quantized_checkpoint: str,
    dataset_path: str,
    split: str = "val",
    imgsz: int = 640,
    device: str = "auto",
    max_map50_drop: float = 0.01,
    strict: bool = False,
) -> dict[str, Any]:
    """Compare accuracy and file size between original and INT8-quantized checkpoints."""
    inp = QuantizeReportInput(
        original_checkpoint=original_checkpoint,
        quantized_checkpoint=quantized_checkpoint,
        dataset_path=Path(dataset_path),
        split=split,
        imgsz=imgsz,
        device=device,
        max_map50_drop=max_map50_drop,
        strict=strict,
    )
    with tool_event(
        "quantize_report",
        original_checkpoint=original_checkpoint,
        quantized_checkpoint=quantized_checkpoint,
        dataset_path=dataset_path,
    ):
        return _run_quantize_report(inp).model_dump(mode="json")


def _run_quantize_report(inp: QuantizeReportInput) -> QuantizeReportOutput:
    t0 = time.perf_counter()

    orig_path = resolve_checkpoint(inp.original_checkpoint)
    quant_path = resolve_checkpoint(inp.quantized_checkpoint)

    orig_out = _run_eval(
        EvalRunInput(
            checkpoint=str(orig_path),
            dataset_path=inp.dataset_path,
            split=inp.split,
            imgsz=inp.imgsz,
            device=inp.device,
        )
    )
    quant_out = _run_eval(
        EvalRunInput(
            checkpoint=str(quant_path),
            dataset_path=inp.dataset_path,
            split=inp.split,
            imgsz=inp.imgsz,
            device=inp.device,
        )
    )

    elapsed = time.perf_counter() - t0
    orig_size = orig_path.stat().st_size
    quant_size = quant_path.stat().st_size
    size_reduction = ((orig_size - quant_size) / orig_size * 100) if orig_size > 0 else 0.0

    map50_delta = quant_out.map50 - orig_out.map50
    accuracy_drop = orig_out.map50 - quant_out.map50
    if accuracy_drop > inp.max_map50_drop:
        verdict = "regressed"
    elif map50_delta > inp.max_map50_drop:
        verdict = "pass"
    else:
        verdict = "fail"

    if verdict == "regressed" and inp.strict:
        raise FovuxExportParityError(
            "Quantized checkpoint regressed beyond the configured tolerance.",
            hint=(
                f"Observed map50 drop {accuracy_drop:.4f} exceeds max_map50_drop "
                f"{inp.max_map50_drop:.4f}."
            ),
        )

    return QuantizeReportOutput(
        original_checkpoint=str(orig_path),
        quantized_checkpoint=str(quant_path),
        original_map50=orig_out.map50,
        quantized_map50=quant_out.map50,
        map50_delta=map50_delta,
        verdict=verdict,
        original_size_bytes=orig_size,
        quantized_size_bytes=quant_size,
        size_reduction_pct=size_reduction,
        report_duration_seconds=elapsed,
    )
