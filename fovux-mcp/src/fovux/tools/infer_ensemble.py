"""infer_ensemble — run multiple checkpoints and fuse detections."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.schemas.inference import InferEnsembleInput, InferEnsembleOutput
from fovux.server import mcp
from fovux.tools.infer_image import _parse_detections


@mcp.tool()
def infer_ensemble(
    checkpoints: list[str],
    image_path: str,
    fusion_method: str = "wbf",
    weights: list[float] | None = None,
    imgsz: int = 640,
    conf: float = 0.25,
    device: str = "auto",
) -> dict[str, Any]:
    """Run ensemble inference and return fused detections."""
    inp = InferEnsembleInput(
        checkpoints=checkpoints,
        image_path=Path(image_path),
        fusion_method=fusion_method,  # type: ignore[arg-type]
        weights=weights,
        imgsz=imgsz,
        conf=conf,
        device=device,
    )
    with tool_event("infer_ensemble", checkpoints=checkpoints):
        return _run_infer_ensemble(inp).model_dump(mode="json")


def _run_infer_ensemble(inp: InferEnsembleInput) -> InferEnsembleOutput:
    detections: list[dict[str, object]] = []
    for checkpoint in inp.checkpoints:
        detections.extend(_predict_checkpoint(checkpoint, inp))
    fused = _fuse_detections(detections)
    return InferEnsembleOutput(
        checkpoints=inp.checkpoints,
        image_path=inp.image_path,
        fusion_method=inp.fusion_method,
        detections=fused,
        detection_count=len(fused),
    )


def _predict_checkpoint(checkpoint: str, inp: InferEnsembleInput) -> list[dict[str, object]]:
    model = load_yolo_model(resolve_checkpoint(checkpoint))
    result = model.predict(
        source=str(inp.image_path),
        imgsz=inp.imgsz,
        conf=inp.conf,
        device=inp.device,
        verbose=False,
    )[0]
    return [detection.model_dump(mode="json") for detection in _parse_detections(result)]


def _fuse_detections(detections: list[dict[str, object]]) -> list[dict[str, object]]:
    fused: list[dict[str, object]] = []
    for detection in sorted(
        detections,
        key=lambda item: cast(float, item.get("confidence", 0.0)),
        reverse=True,
    ):
        if any(_same_class_iou(detection, existing) > 0.5 for existing in fused):
            continue
        fused.append(detection)
    return fused


def _same_class_iou(left: dict[str, object], right: dict[str, object]) -> float:
    if left.get("class_id") != right.get("class_id"):
        return 0.0
    left_box = left.get("bbox_xyxy")
    right_box = right.get("bbox_xyxy")
    if not isinstance(left_box, list) or not isinstance(right_box, list):
        return 0.0
    if len(left_box) < 4 or len(right_box) < 4:
        return 0.0
    lx1, ly1, lx2, ly2 = [float(value) for value in left_box[:4]]
    rx1, ry1, rx2, ry2 = [float(value) for value in right_box[:4]]
    ix1, iy1 = max(lx1, rx1), max(ly1, ry1)
    ix2, iy2 = min(lx2, rx2), min(ly2, ry2)
    intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    left_area = max(0.0, lx2 - lx1) * max(0.0, ly2 - ly1)
    right_area = max(0.0, rx2 - rx1) * max(0.0, ry2 - ry1)
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0
