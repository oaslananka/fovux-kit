"""infer_image — run YOLO inference on a single image."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any

from PIL import Image

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.errors import FovuxCheckpointNotFoundError, FovuxInferenceError
from fovux.core.paths import FovuxPaths, get_fovux_home
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.core.validation import ensure_writable_output
from fovux.schemas.inference import Detection, InferImageInput, InferImageOutput
from fovux.server import mcp


@mcp.tool()
def infer_image(
    checkpoint: str,
    image_path: str,
    imgsz: int = 640,
    conf: float = 0.25,
    iou: float = 0.45,
    device: str = "auto",
    save_image: bool = False,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Run inference on a single image and return structured detections."""
    inp = InferImageInput(
        checkpoint=checkpoint,
        image_path=Path(image_path),
        imgsz=imgsz,
        conf=conf,
        iou=iou,
        device=device,
        save_image=save_image,
        output_path=Path(output_path) if output_path else None,
    )
    with tool_event("infer_image", checkpoint=checkpoint, image_path=image_path):
        return _run_infer_image(inp).model_dump(mode="json")


def _run_infer_image(inp: InferImageInput) -> InferImageOutput:
    checkpoint = resolve_checkpoint(inp.checkpoint)
    image_path = inp.image_path.expanduser().resolve()
    if not image_path.exists():
        raise FovuxInferenceError(
            f"Image path not found: {image_path}",
            hint="Provide a valid local image path for single-image inference.",
        )

    try:
        t0 = perf_counter()
        result = _predict_image(checkpoint, image_path, inp)
        elapsed = perf_counter() - t0
    except FovuxCheckpointNotFoundError:
        raise
    except Exception as exc:
        raise FovuxInferenceError(
            f"Image inference failed for {image_path.name}.",
            hint="Verify the checkpoint and input image are readable by Ultralytics.",
        ) from exc

    detections = _parse_detections(result)
    counts = Counter(det.class_name for det in detections)

    rendered_path: Path | None = None
    if inp.save_image:
        rendered_path = _save_visualization(result, image_path, inp.output_path)

    return InferImageOutput(
        checkpoint=str(checkpoint),
        image_path=image_path,
        detections=detections,
        detection_count=len(detections),
        detections_by_class=dict(counts),
        inference_duration_seconds=elapsed,
        output_path=rendered_path,
    )


def _predict_image(checkpoint: Path, image_path: Path, inp: InferImageInput) -> object:
    model = load_yolo_model(checkpoint)
    results = model.predict(
        source=str(image_path),
        imgsz=inp.imgsz,
        conf=inp.conf,
        iou=inp.iou,
        device=inp.device,
        verbose=False,
    )
    return results[0]


def _parse_detections(result: object) -> list[Detection]:
    names = getattr(result, "names", {})
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []

    cls_values = _tensor_to_list(getattr(boxes, "cls", []))
    conf_values = _tensor_to_list(getattr(boxes, "conf", []))
    xyxy_values = _tensor_to_nested_list(getattr(boxes, "xyxy", []))

    detections: list[Detection] = []
    if xyxy_values:
        for idx, bbox in enumerate(xyxy_values):
            class_id = int(cls_values[idx]) if idx < len(cls_values) else 0
            class_name = (
                names.get(class_id, str(class_id)) if isinstance(names, dict) else str(class_id)
            )
            confidence = float(conf_values[idx]) if idx < len(conf_values) else 0.0
            detections.append(
                Detection(
                    class_id=class_id,
                    class_name=class_name,
                    confidence=confidence,
                    bbox_xyxy=[float(v) for v in bbox[:4]],
                )
            )
        return detections

    raw_rows = _tensor_to_nested_list(getattr(boxes, "data", []))
    for row in raw_rows:
        if len(row) < 6:
            continue
        class_id = int(row[5])
        class_name = (
            names.get(class_id, str(class_id)) if isinstance(names, dict) else str(class_id)
        )
        detections.append(
            Detection(
                class_id=class_id,
                class_name=class_name,
                confidence=float(row[4]),
                bbox_xyxy=[float(v) for v in row[:4]],
            )
        )
    return detections


def _save_visualization(result: object, image_path: Path, output_path: Path | None) -> Path:
    target = ensure_writable_output(
        output_path or (FovuxPaths(get_fovux_home()).exports / f"{image_path.stem}_pred.jpg")
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    rendered = result.plot() if hasattr(result, "plot") else None
    if rendered is None:
        target.write_bytes(image_path.read_bytes())
        return target
    Image.fromarray(rendered).save(target)
    return target


def _tensor_to_list(value: object) -> list[float]:
    if value is None:
        return []
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    if hasattr(value, "tolist"):
        raw = value.tolist()
    else:
        raw = value
    if isinstance(raw, list):
        return [float(item) for item in raw]
    return []


def _tensor_to_nested_list(value: object) -> list[list[float]]:
    if value is None:
        return []
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "numpy"):
        value = value.numpy()
    if hasattr(value, "tolist"):
        raw = value.tolist()
    else:
        raw = value
    if not isinstance(raw, list):
        return []
    rows: list[list[float]] = []
    for row in raw:
        if isinstance(row, list | tuple):
            rows.append([float(item) for item in row])
    return rows
