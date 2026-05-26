"""eval_run — run YOLO validation and return aggregate metrics."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.errors import FovuxDatasetNotFoundError
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.schemas.eval import EvalRunInput, EvalRunOutput, PerClassStat
from fovux.server import mcp


@mcp.tool()
def eval_run(
    checkpoint: str,
    dataset_path: str,
    split: str = "val",
    batch: int = 16,
    imgsz: int = 640,
    device: str = "auto",
    conf: float = 0.25,
    iou: float = 0.45,
    task: str = "detect",
) -> dict[str, Any]:
    """Run YOLO validation and return aggregate metrics plus a per-class breakdown."""
    inp = EvalRunInput(
        checkpoint=checkpoint,
        dataset_path=Path(dataset_path),
        split=split,
        batch=batch,
        imgsz=imgsz,
        device=device,
        conf=conf,
        iou=iou,
        task=task,  # type: ignore[arg-type]
    )
    with tool_event("eval_run", checkpoint=checkpoint, dataset_path=dataset_path, split=split):
        return _run_eval(inp).model_dump(mode="json")


def _run_eval(inp: EvalRunInput) -> EvalRunOutput:
    dataset_path = inp.dataset_path.expanduser().resolve()
    if not dataset_path.exists():
        raise FovuxDatasetNotFoundError(str(dataset_path))

    ckpt_path = resolve_checkpoint(inp.checkpoint)

    t0 = time.perf_counter()
    results = _yolo_val(ckpt_path, dataset_path, inp)
    elapsed = time.perf_counter() - t0

    return _parse_val_results(inp, results, elapsed, ckpt_path)


def _resolve_checkpoint(checkpoint: str) -> Path:
    """Compatibility shim for tests and older private imports."""
    return resolve_checkpoint(checkpoint)


def _yolo_val(ckpt_path: Path, dataset_path: Path, inp: EvalRunInput) -> object:
    model = load_yolo_model(ckpt_path)
    data_yaml = dataset_path / "data.yaml"
    return model.val(
        data=str(data_yaml),
        split=inp.split,
        batch=inp.batch,
        imgsz=inp.imgsz,
        device=inp.device,
        conf=inp.conf,
        iou=inp.iou,
        verbose=False,
    )


def _parse_val_results(
    inp: EvalRunInput,
    results: object,
    elapsed: float,
    ckpt_path: Path,
) -> EvalRunOutput:
    box = getattr(results, "box", results)
    names: dict[int, str] = getattr(results, "names", {})

    map50 = float(getattr(box, "map50", 0.0) or 0.0)
    map50_95 = float(getattr(box, "map", 0.0) or 0.0)
    precision = float(getattr(box, "mp", 0.0) or 0.0)
    recall = float(getattr(box, "mr", 0.0) or 0.0)

    per_class: list[PerClassStat] = []
    class_indices = getattr(box, "ap_class_index", [])
    ap50_list = getattr(box, "ap50", [])
    ap_list = getattr(box, "ap", [])
    p_list = getattr(box, "p", [])
    r_list = getattr(box, "r", [])

    for i, cls_id in enumerate(class_indices):
        cls_id = int(cls_id)
        per_class.append(
            PerClassStat(
                class_id=cls_id,
                class_name=names.get(cls_id, str(cls_id)),
                images=0,
                instances=0,
                precision=float(p_list[i]) if i < len(p_list) else 0.0,
                recall=float(r_list[i]) if i < len(r_list) else 0.0,
                map50=float(ap50_list[i]) if i < len(ap50_list) else 0.0,
                map50_95=float(ap_list[i]) if i < len(ap_list) else 0.0,
            )
        )

    results_dir = getattr(results, "save_dir", None)

    return EvalRunOutput(
        checkpoint=str(ckpt_path),
        dataset_path=inp.dataset_path,
        split=inp.split,
        map50=map50,
        map50_95=map50_95,
        precision=precision,
        recall=recall,
        per_class=per_class,
        eval_duration_seconds=elapsed,
        results_dir=Path(results_dir) if results_dir else None,
    )
