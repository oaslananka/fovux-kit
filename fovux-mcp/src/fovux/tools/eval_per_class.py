"""eval_per_class — per-class breakdown sorted by chosen metric."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fovux.core.tooling import tool_event
from fovux.schemas.eval import EvalPerClassInput, EvalPerClassOutput, EvalRunInput
from fovux.server import mcp


@mcp.tool()
def eval_per_class(
    checkpoint: str,
    dataset_path: str,
    split: str = "val",
    batch: int = 16,
    imgsz: int = 640,
    device: str = "auto",
    conf: float = 0.25,
    iou: float = 0.45,
    sort_by: str = "map50",
    ascending: bool = True,
) -> dict[str, Any]:
    """Return per-class evaluation stats sorted by a chosen metric."""
    inp = EvalPerClassInput(
        checkpoint=checkpoint,
        dataset_path=Path(dataset_path),
        split=split,
        batch=batch,
        imgsz=imgsz,
        device=device,
        conf=conf,
        iou=iou,
        sort_by=sort_by,  # type: ignore[arg-type]
        ascending=ascending,
    )
    with tool_event(
        "eval_per_class",
        checkpoint=checkpoint,
        dataset_path=dataset_path,
        split=split,
        sort_by=sort_by,
    ):
        return _run_eval_per_class(inp).model_dump(mode="json")


def _run_eval_per_class(inp: EvalPerClassInput) -> EvalPerClassOutput:
    from fovux.tools.eval_run import _run_eval

    eval_out = _run_eval(
        EvalRunInput(
            checkpoint=inp.checkpoint,
            dataset_path=inp.dataset_path,
            split=inp.split,
            batch=inp.batch,
            imgsz=inp.imgsz,
            device=inp.device,
            conf=inp.conf,
            iou=inp.iou,
        )
    )

    sort_key = inp.sort_by
    per_class = sorted(
        eval_out.per_class,
        key=lambda s: getattr(s, sort_key) if sort_key != "class_name" else s.class_name,
        reverse=not inp.ascending,
    )

    worst = sorted(eval_out.per_class, key=lambda stat: stat.map50)[:5]

    return EvalPerClassOutput(
        checkpoint=inp.checkpoint,
        per_class=per_class,
        worst_classes=worst,
        eval_duration_seconds=eval_out.eval_duration_seconds,
    )
