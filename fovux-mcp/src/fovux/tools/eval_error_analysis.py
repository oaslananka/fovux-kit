"""eval_error_analysis — confusion matrix and worst-error samples."""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.dataset_utils import parse_yolo_label
from fovux.core.errors import FovuxDatasetNotFoundError
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.schemas.eval import (
    ConfusionEntry,
    ErrorSample,
    EvalErrorAnalysisInput,
    EvalErrorAnalysisOutput,
)
from fovux.server import mcp


@mcp.tool()
def eval_error_analysis(
    checkpoint: str,
    dataset_path: str,
    split: str = "val",
    top_n: int = 10,
    imgsz: int = 640,
    device: str = "auto",
    conf: float = 0.25,
    iou: float = 0.45,
) -> dict[str, Any]:
    """Analyze model errors: confusion matrix entries and worst false-positive/negative images."""
    inp = EvalErrorAnalysisInput(
        checkpoint=checkpoint,
        dataset_path=Path(dataset_path),
        split=split,
        top_n=top_n,
        imgsz=imgsz,
        device=device,
        conf=conf,
        iou=iou,
    )
    with tool_event(
        "eval_error_analysis",
        checkpoint=checkpoint,
        dataset_path=dataset_path,
        split=split,
    ):
        return _run_error_analysis(inp).model_dump(mode="json")


def _run_error_analysis(inp: EvalErrorAnalysisInput) -> EvalErrorAnalysisOutput:
    dataset_path = inp.dataset_path.expanduser().resolve()
    if not dataset_path.exists():
        raise FovuxDatasetNotFoundError(str(dataset_path))

    ckpt_path = resolve_checkpoint(inp.checkpoint)

    t0 = time.perf_counter()
    confusion_entries, top_errors, fp_count, fn_count = _yolo_error_analysis(
        ckpt_path, dataset_path, inp
    )
    elapsed = time.perf_counter() - t0

    return EvalErrorAnalysisOutput(
        checkpoint=str(ckpt_path),
        confusion_matrix=confusion_entries,
        top_errors=top_errors,
        false_positive_count=fp_count,
        false_negative_count=fn_count,
        eval_duration_seconds=elapsed,
    )


def _yolo_error_analysis(
    ckpt_path: Path,
    dataset_path: Path,
    inp: EvalErrorAnalysisInput,
) -> tuple[list[ConfusionEntry], list[ErrorSample], int, int]:
    model = load_yolo_model(ckpt_path)
    results = model.val(
        data=str(dataset_path / "data.yaml"),
        split=inp.split,
        imgsz=inp.imgsz,
        device=inp.device,
        conf=inp.conf,
        iou=inp.iou,
        verbose=False,
        save_json=True,
    )

    names: dict[int, str] = getattr(results, "names", {})
    cm_obj = getattr(results, "confusion_matrix", None)
    confusion_entries: list[ConfusionEntry] = []
    fp_count = 0
    fn_count = 0

    if cm_obj is not None:
        matrix = getattr(cm_obj, "matrix", None)
        if matrix is not None:
            n = matrix.shape[0]
            bg_idx = n - 1
            for true_i in range(n):
                for pred_i in range(n):
                    if true_i == pred_i:
                        continue
                    count = int(matrix[pred_i, true_i])
                    if count == 0:
                        continue
                    true_name = names.get(true_i, "background") if true_i < bg_idx else "background"
                    pred_name = names.get(pred_i, "background") if pred_i < bg_idx else "background"
                    confusion_entries.append(
                        ConfusionEntry(
                            true_class=true_name,
                            predicted_class=pred_name,
                            count=count,
                        )
                    )
                    if pred_i == bg_idx:
                        fn_count += count
                    elif true_i == bg_idx:
                        fp_count += count

    confusion_entries.sort(key=lambda e: e.count, reverse=True)

    top_errors = _extract_worst_samples(
        results=results,
        dataset_path=dataset_path,
        split=inp.split,
        top_n=inp.top_n,
        names=names,
    )

    return confusion_entries[: inp.top_n], top_errors, fp_count, fn_count


@dataclass(frozen=True)
class _GroundTruthBox:
    class_id: int
    xyxy: tuple[float, float, float, float]


@dataclass(frozen=True)
class _GroundTruthSample:
    image_path: Path
    boxes: tuple[_GroundTruthBox, ...]


def _extract_worst_samples(
    *,
    results: object,
    dataset_path: Path,
    split: str,
    top_n: int,
    names: dict[int, str],
) -> list[ErrorSample]:
    jdict = getattr(results, "jdict", []) or []
    samples = _load_ground_truth_samples(dataset_path, split)
    if not samples:
        return []

    grouped_predictions: dict[str, list[dict[str, Any]]] = {}
    for prediction in jdict:
        if not isinstance(prediction, dict):
            continue
        sample_key = _resolve_sample_key(prediction, samples)
        if sample_key is None:
            continue
        grouped_predictions.setdefault(sample_key, []).append(prediction)

    scored_errors: list[tuple[float, ErrorSample]] = []
    for sample_key, sample in samples.items():
        predictions = grouped_predictions.get(sample_key, [])
        gt_counts = Counter(box.class_id for box in sample.boxes)
        pred_counts = Counter(
            int(prediction.get("category_id", -1))
            for prediction in predictions
            if isinstance(prediction.get("category_id"), int)
        )

        for prediction in predictions:
            pred_class = prediction.get("category_id", -1)
            if not isinstance(pred_class, int):
                continue
            confidence = float(prediction.get("score", 0.0))
            pred_bbox = _prediction_bbox(prediction)
            matching_gt = [box for box in sample.boxes if box.class_id == pred_class]
            best_iou = (
                max((_bbox_iou(pred_bbox, box.xyxy) for box in matching_gt), default=0.0)
                if pred_bbox is not None
                else 0.0
            )
            if matching_gt and best_iou > 0.1:
                continue
            true_class = names.get(pred_class, str(pred_class)) if matching_gt else "background"
            scored_errors.append(
                (
                    2.0 + confidence - best_iou,
                    ErrorSample(
                        image_path=sample.image_path,
                        true_class=true_class,
                        predicted_class=names.get(pred_class, str(pred_class)),
                        confidence=confidence,
                        iou=round(best_iou, 4),
                    ),
                )
            )

        for class_id, count in gt_counts.items():
            missing = max(count - pred_counts.get(class_id, 0), 0)
            for _ in range(missing):
                scored_errors.append(
                    (
                        1.0,
                        ErrorSample(
                            image_path=sample.image_path,
                            true_class=names.get(class_id, str(class_id)),
                            predicted_class="background",
                            confidence=0.0,
                            iou=0.0,
                        ),
                    ),
                )

    scored_errors.sort(key=lambda item: item[0], reverse=True)
    return [sample for _, sample in scored_errors[:top_n]]


def _load_ground_truth_samples(dataset_path: Path, split: str) -> dict[str, _GroundTruthSample]:
    images_dir = dataset_path / "images" / split
    labels_dir = dataset_path / "labels" / split
    if not images_dir.exists() or not labels_dir.exists():
        return {}

    samples: dict[str, _GroundTruthSample] = {}
    label_files = sorted(labels_dir.glob("*.txt"))
    for index, label_file in enumerate(label_files):
        image_path = _match_image_path(images_dir, label_file.stem)
        if image_path is None:
            continue
        with Image.open(image_path) as image:
            width, height = image.size
        boxes = tuple(
            _GroundTruthBox(
                class_id=class_id,
                xyxy=_yolo_to_xyxy(cx, cy, box_width, box_height, width, height),
            )
            for class_id, cx, cy, box_width, box_height in parse_yolo_label(label_file)
        )
        sample = _GroundTruthSample(image_path=image_path, boxes=boxes)
        for alias in {label_file.stem, str(index), str(index + 1)}:
            samples[alias] = sample
    return samples


def _resolve_sample_key(
    prediction: dict[str, Any], samples: dict[str, _GroundTruthSample]
) -> str | None:
    candidates: list[str] = []
    for key in ("image_id", "file_name", "image"):
        raw = prediction.get(key)
        if raw is None:
            continue
        value = str(raw).strip()
        if not value:
            continue
        candidates.append(Path(value).stem)
        candidates.append(value)
    for candidate in candidates:
        if candidate in samples:
            return candidate
    return None


def _match_image_path(images_dir: Path, stem: str) -> Path | None:
    for extension in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
        candidate = images_dir / f"{stem}{extension}"
        if candidate.exists():
            return candidate
    return None


def _yolo_to_xyxy(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    image_width: int,
    image_height: int,
) -> tuple[float, float, float, float]:
    half_width = width * image_width / 2
    half_height = height * image_height / 2
    x_center = center_x * image_width
    y_center = center_y * image_height
    return (
        x_center - half_width,
        y_center - half_height,
        x_center + half_width,
        y_center + half_height,
    )


def _prediction_bbox(prediction: dict[str, Any]) -> tuple[float, float, float, float] | None:
    bbox = prediction.get("bbox")
    if not isinstance(bbox, list) or len(bbox) < 4:
        return None
    x, y, width, height = bbox[:4]
    if not all(isinstance(value, (int, float)) for value in (x, y, width, height)):
        return None
    left = float(x)
    top = float(y)
    return (left, top, left + float(width), top + float(height))


def _bbox_iou(
    left: tuple[float, float, float, float] | None,
    right: tuple[float, float, float, float],
) -> float:
    if left is None:
        return 0.0
    ax1, ay1, ax2, ay2 = left
    bx1, by1, bx2, by2 = right
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(inter_x2 - inter_x1, 0.0)
    inter_h = max(inter_y2 - inter_y1, 0.0)
    intersection = inter_w * inter_h
    if intersection <= 0:
        return 0.0
    area_left = max(ax2 - ax1, 0.0) * max(ay2 - ay1, 0.0)
    area_right = max(bx2 - bx1, 0.0) * max(by2 - by1, 0.0)
    union = area_left + area_right - intersection
    if union <= 0:
        return 0.0
    return intersection / union
