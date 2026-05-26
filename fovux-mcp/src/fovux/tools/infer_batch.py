"""infer_batch — run local batch inference over a directory of images."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.dataset_utils import find_images
from fovux.core.errors import FovuxInferenceError
from fovux.core.paths import FovuxPaths, get_fovux_home
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.core.validation import ensure_writable_output
from fovux.schemas.inference import (
    BatchDetectionSummary,
    InferBatchInput,
    InferBatchOutput,
)
from fovux.server import mcp
from fovux.tools.infer_image import _parse_detections


@mcp.tool()
def infer_batch(
    checkpoint: str,
    input_dir: str,
    output_dir: str | None = None,
    imgsz: int = 640,
    conf: float = 0.25,
    save_annotated: bool = True,
    export_format: str = "json",
    device: str = "auto",
    batch_size: int = 32,
) -> dict[str, Any]:
    """Run inference over all images in a directory and persist a structured manifest."""
    inp = InferBatchInput(
        checkpoint=checkpoint,
        input_dir=Path(input_dir),
        output_dir=Path(output_dir) if output_dir else None,
        imgsz=imgsz,
        conf=conf,
        save_annotated=save_annotated,
        export_format=export_format,  # type: ignore[arg-type]
        device=device,
        batch_size=batch_size,
    )
    with tool_event("infer_batch", checkpoint=checkpoint, input_dir=input_dir):
        return _run_infer_batch(inp).model_dump(mode="json")


def _run_infer_batch(inp: InferBatchInput) -> InferBatchOutput:
    checkpoint = resolve_checkpoint(inp.checkpoint)
    input_dir = inp.input_dir.expanduser().resolve()
    if not input_dir.exists():
        raise FovuxInferenceError(
            f"Input directory not found: {input_dir}",
            hint="Point infer_batch at a directory that contains images.",
        )

    output_dir = ensure_writable_output(
        inp.output_dir or (FovuxPaths(get_fovux_home()).exports / f"{checkpoint.stem}_batch")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    annotated_dir = output_dir / "annotated"
    if inp.save_annotated:
        annotated_dir.mkdir(parents=True, exist_ok=True)

    image_paths = find_images(input_dir)
    if not image_paths:
        raise FovuxInferenceError(
            f"No images were found under {input_dir}.",
            hint="Supported formats include jpg, png, bmp, webp, tiff, and tif.",
        )

    model = load_yolo_model(checkpoint)
    results = model.predict(
        source=[str(image_path) for image_path in image_paths],
        imgsz=inp.imgsz,
        conf=inp.conf,
        device=inp.device,
        batch=inp.batch_size,
        verbose=False,
    )

    preview: list[BatchDetectionSummary] = []
    manifest_records: list[dict[str, object]] = []
    total_detections = 0

    for image_path, result in zip(image_paths, results, strict=False):
        detections = _parse_detections(result)
        total_detections += len(detections)
        counts = Counter(detection.class_name for detection in detections)
        rendered_path: Path | None = None
        if inp.save_annotated and hasattr(result, "plot"):
            from PIL import Image

            rendered_path = annotated_dir / image_path.name
            Image.fromarray(result.plot()).save(rendered_path)

        preview.append(
            BatchDetectionSummary(
                image_path=image_path,
                detection_count=len(detections),
                detections_by_class=dict(counts),
                output_path=rendered_path,
            )
        )
        manifest_records.append(
            {
                "image_path": str(image_path),
                "detection_count": len(detections),
                "detections_by_class": dict(counts),
                "detections": [detection.model_dump(mode="json") for detection in detections],
                "output_path": str(rendered_path) if rendered_path else None,
            }
        )

    manifest_path = _write_manifest(output_dir, inp.export_format, manifest_records)
    return InferBatchOutput(
        checkpoint=str(checkpoint),
        input_dir=input_dir,
        output_dir=output_dir,
        export_format=inp.export_format,
        processed_images=len(image_paths),
        detection_count=total_detections,
        manifest_path=manifest_path,
        annotated_dir=annotated_dir if inp.save_annotated else None,
        preview=preview[:10],
    )


def _write_manifest(
    output_dir: Path,
    export_format: str,
    manifest_records: list[dict[str, object]],
) -> Path:
    if export_format == "csv":
        target = output_dir / "predictions.csv"
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["image_path", "detection_count", "detections_by_class", "output_path"],
            )
            writer.writeheader()
            for record in manifest_records:
                writer.writerow(
                    {
                        "image_path": record["image_path"],
                        "detection_count": record["detection_count"],
                        "detections_by_class": json.dumps(record["detections_by_class"]),
                        "output_path": record["output_path"],
                    }
                )
        return target

    if export_format == "yolo_labels":
        labels_dir = output_dir / "labels"
        labels_dir.mkdir(parents=True, exist_ok=True)
        for record in manifest_records:
            image_path = Path(str(record["image_path"]))
            detections = record["detections"]
            lines = []
            if isinstance(detections, list):
                for detection in detections:
                    if not isinstance(detection, dict):
                        continue
                    bbox = detection.get("bbox_xyxy")
                    class_id = detection.get("class_id")
                    confidence = detection.get("confidence")
                    if not isinstance(bbox, list) or len(bbox) < 4:
                        continue
                    if not isinstance(class_id, int) or not isinstance(confidence, (int, float)):
                        continue
                    lines.append(
                        " ".join(
                            [
                                str(class_id),
                                *(f"{float(value):.4f}" for value in bbox[:4]),
                                f"{float(confidence):.4f}",
                            ]
                        )
                    )
            (labels_dir / f"{image_path.stem}.txt").write_text("\n".join(lines), encoding="utf-8")
        return labels_dir

    target = output_dir / "predictions.json"
    target.write_text(json.dumps(manifest_records, indent=2), encoding="utf-8")
    return target
