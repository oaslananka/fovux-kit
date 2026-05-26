"""model_compare_visual — render side-by-side checkpoint predictions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.paths import FovuxPaths, get_fovux_home
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.schemas.inference import ModelCompareVisualInput, ModelCompareVisualOutput
from fovux.server import mcp
from fovux.tools.infer_image import _parse_detections


@mcp.tool()
def model_compare_visual(
    checkpoint_a: str,
    checkpoint_b: str,
    image_path: str,
    output_path: str | None = None,
    imgsz: int = 640,
    conf: float = 0.25,
    device: str = "auto",
) -> dict[str, Any]:
    """Compare two checkpoints visually on a single image."""
    inp = ModelCompareVisualInput(
        checkpoint_a=checkpoint_a,
        checkpoint_b=checkpoint_b,
        image_path=Path(image_path),
        output_path=Path(output_path) if output_path else None,
        imgsz=imgsz,
        conf=conf,
        device=device,
    )
    with tool_event("model_compare_visual", checkpoint_a=checkpoint_a, checkpoint_b=checkpoint_b):
        return _run_model_compare_visual(inp).model_dump(mode="json")


def _run_model_compare_visual(inp: ModelCompareVisualInput) -> ModelCompareVisualOutput:
    comparison_name = (
        f"{inp.image_path.stem}_{Path(inp.checkpoint_a).stem}_vs_{Path(inp.checkpoint_b).stem}.png"
    )
    output_path = inp.output_path or (
        FovuxPaths(get_fovux_home()).home / "comparisons" / comparison_name
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    detections_a = _predict_detections(inp.checkpoint_a, inp.image_path, inp)
    detections_b = _predict_detections(inp.checkpoint_b, inp.image_path, inp)
    _draw_comparison(inp.image_path, detections_a, detections_b, output_path)
    return ModelCompareVisualOutput(
        checkpoint_a=inp.checkpoint_a,
        checkpoint_b=inp.checkpoint_b,
        image_path=inp.image_path,
        output_path=output_path,
        detections_a=len(detections_a),
        detections_b=len(detections_b),
    )


def _predict_detections(
    checkpoint: str,
    image_path: Path,
    inp: ModelCompareVisualInput,
) -> list[dict[str, object]]:
    model = load_yolo_model(resolve_checkpoint(checkpoint))
    result = model.predict(
        source=str(image_path),
        imgsz=inp.imgsz,
        conf=inp.conf,
        device=inp.device,
        verbose=False,
    )[0]
    return [detection.model_dump(mode="json") for detection in _parse_detections(result)]


def _draw_comparison(
    image_path: Path,
    left_detections: list[dict[str, object]],
    right_detections: list[dict[str, object]],
    output_path: Path,
) -> None:
    with Image.open(image_path).convert("RGB") as image:
        left = image.copy()
        right = image.copy()
    _draw_boxes(left, left_detections, "red")
    _draw_boxes(right, right_detections, "lime")
    canvas = Image.new("RGB", (left.width + right.width, max(left.height, right.height)), "white")
    canvas.paste(left, (0, 0))
    canvas.paste(right, (left.width, 0))
    canvas.save(output_path)


def _draw_boxes(image: Image.Image, detections: list[dict[str, object]], color: str) -> None:
    draw = ImageDraw.Draw(image)
    for detection in detections:
        bbox = detection.get("bbox_xyxy")
        if not isinstance(bbox, list) or len(bbox) < 4:
            continue
        box = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
        draw.rectangle(box, outline=color, width=2)
        label = str(detection.get("class_name", "object"))
        draw.text((float(bbox[0]), max(0.0, float(bbox[1]) - 10)), label, fill=color)
