"""eval_compare — evaluate multiple checkpoints side by side."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fovux.core.tooling import tool_event
from fovux.schemas.eval import (
    CheckpointComparison,
    EvalCompareInput,
    EvalCompareOutput,
    EvalRunInput,
)
from fovux.server import mcp


@mcp.tool()
def eval_compare(
    checkpoints: list[str],
    dataset_path: str,
    split: str = "val",
    batch: int = 16,
    imgsz: int = 640,
    device: str = "auto",
    conf: float = 0.25,
    iou: float = 0.45,
) -> dict[str, Any]:
    """Evaluate multiple checkpoints on the same dataset and rank them."""
    inp = EvalCompareInput(
        checkpoints=checkpoints,
        dataset_path=Path(dataset_path),
        split=split,
        batch=batch,
        imgsz=imgsz,
        device=device,
        conf=conf,
        iou=iou,
    )
    with tool_event(
        "eval_compare",
        checkpoints=checkpoints,
        dataset_path=dataset_path,
        split=split,
    ):
        return _run_eval_compare(inp).model_dump(mode="json")


def _run_eval_compare(inp: EvalCompareInput) -> EvalCompareOutput:
    from fovux.tools.eval_run import _run_eval

    comparisons: list[CheckpointComparison] = []

    for ckpt in inp.checkpoints:
        out = _run_eval(
            EvalRunInput(
                checkpoint=ckpt,
                dataset_path=inp.dataset_path,
                split=inp.split,
                batch=inp.batch,
                imgsz=inp.imgsz,
                device=inp.device,
                conf=inp.conf,
                iou=inp.iou,
            )
        )
        comparisons.append(
            CheckpointComparison(
                checkpoint=ckpt,
                map50=out.map50,
                map50_95=out.map50_95,
                precision=out.precision,
                recall=out.recall,
                eval_duration_seconds=out.eval_duration_seconds,
            )
        )

    best_map50 = max(comparisons, key=lambda c: c.map50).checkpoint if comparisons else ""
    best_map50_95 = max(comparisons, key=lambda c: c.map50_95).checkpoint if comparisons else ""

    return EvalCompareOutput(
        dataset_path=inp.dataset_path,
        split=inp.split,
        results=sorted(comparisons, key=lambda c: c.map50, reverse=True),
        best_map50=best_map50,
        best_map50_95=best_map50_95,
    )
