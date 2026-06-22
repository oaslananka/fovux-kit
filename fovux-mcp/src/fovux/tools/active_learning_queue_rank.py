"""active_learning_queue_rank — rank unlabeled images and populate review queue."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.paths import ensure_fovux_dirs, get_fovux_home
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.schemas.inference import (
    ActiveLearningQueueItem,
    ActiveLearningQueueRankInput,
    ActiveLearningQueueRankOutput,
    Detection,
)
from fovux.server import mcp


@mcp.tool()
def active_learning_queue_rank(
    checkpoint: str,
    unlabeled_pool: str,
    dataset_path: str,
    strategy: str = "entropy",
    limit: int = 50,
    imgsz: int = 640,
    conf: float = 0.25,
    device: str = "auto",
) -> dict[str, Any]:
    """Rank unlabeled images by uncertainty and insert them into the review queue."""
    inp = ActiveLearningQueueRankInput(
        checkpoint=checkpoint,
        unlabeled_pool=Path(unlabeled_pool),
        dataset_path=Path(dataset_path),
        strategy=strategy,  # type: ignore[arg-type]
        limit=limit,
        imgsz=imgsz,
        conf=conf,
        device=device,
    )
    with tool_event(
        "active_learning_queue_rank",
        checkpoint=checkpoint,
        unlabeled_pool=unlabeled_pool,
        dataset_path=dataset_path,
    ):
        output = _run_active_learning_queue_rank(inp)
        return output.model_dump(mode="json")


def _get_dataset_class_counts(dataset_path: Path) -> dict[int, int]:
    counts: dict[int, int] = {}
    labels_dir = dataset_path / "labels"
    if not labels_dir.exists():
        return counts
    for txt_file in labels_dir.rglob("*.txt"):
        try:
            content = txt_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                parts = line.strip().split()
                if parts:
                    class_id = int(parts[0])
                    counts[class_id] = counts.get(class_id, 0) + 1
        except Exception:  # noqa: S112
            continue
    return counts


def _get_existing_labels(image_path: Path) -> list[tuple[int, list[float]]] | None:
    txt_path = image_path.with_suffix(".txt")
    if not txt_path.exists():
        path_str = str(image_path)
        if "images" in path_str:
            txt_path = Path(path_str.replace("images", "labels")).with_suffix(".txt")
    if txt_path.exists():
        labels = []
        try:
            content = txt_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5:
                    class_id = int(parts[0])
                    coords = [float(x) for x in parts[1:5]]
                    labels.append((class_id, coords))
            return labels
        except Exception:  # noqa: S110
            pass
    return None


def _run_active_learning_queue_rank(
    inp: ActiveLearningQueueRankInput,
) -> ActiveLearningQueueRankOutput:
    pool = inp.unlabeled_pool.expanduser().resolve()
    if not pool.exists():
        from fovux.core.errors import FovuxDatasetNotFoundError

        raise FovuxDatasetNotFoundError(f"Unlabeled pool not found: {pool}")

    paths = ensure_fovux_dirs(get_fovux_home())
    registry = get_registry(paths.runs_db)

    # 1. Scan images
    image_exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    images = sorted(path for path in pool.rglob("*") if path.suffix.lower() in image_exts)

    # 2. Load model
    model = load_yolo_model(resolve_checkpoint(inp.checkpoint))

    # 3. Get dataset class counts for underrepresented check & diversity strategy
    counts = _get_dataset_class_counts(inp.dataset_path)

    queue_entries: list[ActiveLearningQueueItem] = []

    for image in images[: inp.limit]:
        # Run inference
        result = model.predict(
            source=str(image),
            imgsz=inp.imgsz,
            conf=inp.conf,
            device=inp.device,
            verbose=False,
        )[0]

        # Extract predictions
        detections: list[Detection] = []
        confidences: list[float] = []

        boxes = getattr(result, "boxes", None)
        if boxes is not None:
            conf_vals = getattr(boxes, "conf", None)
            cls_vals = getattr(boxes, "cls", None)
            xyxy_vals = getattr(boxes, "xyxy", None)

            if conf_vals is not None and cls_vals is not None and xyxy_vals is not None:
                confs = conf_vals.tolist() if hasattr(conf_vals, "tolist") else list(conf_vals)
                clses = cls_vals.tolist() if hasattr(cls_vals, "tolist") else list(cls_vals)
                xyxys = xyxy_vals.tolist() if hasattr(xyxy_vals, "tolist") else list(xyxy_vals)

                names = getattr(result, "names", {})

                for c_val, cl_val, box_val in zip(confs, clses, xyxys, strict=True):
                    confidences.append(float(c_val))
                    class_id = int(cl_val)
                    class_name = names.get(class_id, f"class_{class_id}")
                    # YOLO webviews expect relative coordinates or normalized xyxy for visual
                    # preview
                    orig_shape = getattr(result, "orig_shape", (640, 640))
                    w, h = orig_shape[1], orig_shape[0]
                    norm_xyxy = [
                        box_val[0] / w,
                        box_val[1] / h,
                        box_val[2] / w,
                        box_val[3] / h,
                    ]
                    detections.append(
                        Detection(
                            class_id=class_id,
                            class_name=class_name,
                            confidence=float(c_val),
                            # Convert xyxy [x0, y0, x1, y1] to [x, y, w, h] format for boxes preview
                            bbox_xyxy=[
                                norm_xyxy[0],
                                norm_xyxy[1],
                                norm_xyxy[2] - norm_xyxy[0],
                                norm_xyxy[3] - norm_xyxy[1],
                            ],
                        )
                    )

        # 4. Check conditions for reason tags
        # Check disagreement with existing labels (weak labels)
        existing_labels = _get_existing_labels(image)
        disagreement = False
        if existing_labels is not None:
            pred_classes = [d.class_id for d in detections]
            exist_classes = [label[0] for label in existing_labels]
            if len(pred_classes) != len(exist_classes) or set(pred_classes) != set(exist_classes):
                disagreement = True

        # Check outlier conditions
        outlier = False
        if len(detections) > 10:
            outlier = True
        else:
            for d in detections:
                if len(d.bbox_xyxy) >= 4:
                    box_w, box_h = d.bbox_xyxy[2], d.bbox_xyxy[3]
                    area = box_w * box_h
                    if area < 0.002 or area > 0.8:
                        outlier = True
                        break

        # Check underrepresented classes
        underrepresented = False
        if counts:
            all_counts = list(counts.values())
            threshold = max(5.0, sum(all_counts) / len(all_counts) * 0.5) if all_counts else 5.0
            for d in detections:
                if counts.get(d.class_id, 0) < threshold:
                    underrepresented = True
                    break

        # 5. Compute strategy-based uncertainty score
        if not confidences:
            uncertainty_score = 1.0
        else:
            best = max(confidences)
            if inp.strategy == "least_confident":
                uncertainty_score = 1.0 - best
            elif inp.strategy == "margin" and len(confidences) > 1:
                ordered = sorted(confidences, reverse=True)
                uncertainty_score = 1.0 - (ordered[0] - ordered[1])
            else:  # entropy-like closeness to 0.5
                uncertainty_score = sum(1.0 - abs(c - 0.5) * 2.0 for c in confidences) / len(
                    confidences
                )

        # Apply strategy choice to main score
        if inp.strategy == "diversity":
            if not counts:
                score = uncertainty_score
            else:
                max_count = max(counts.values()) if counts.values() else 1
                pred_counts = [counts.get(d.class_id, 0) for d in detections]
                if pred_counts:
                    score = 1.0 - (sum(pred_counts) / len(pred_counts)) / max_count
                else:
                    score = 0.0
        elif inp.strategy == "error_likelihood":
            if disagreement:
                score = 1.0
            elif outlier:
                score = 0.9
            elif underrepresented:
                score = 0.8
            else:
                score = min(0.7, uncertainty_score)
        else:
            score = uncertainty_score

        # Determine best reason code
        if disagreement:
            reason = "disagreement"
        elif outlier:
            reason = "outlier"
        elif underrepresented:
            reason = "underrepresented_class"
        elif not confidences:
            reason = "no_detections"
        else:
            reason = "low_confidence"

        entry_id = hashlib.md5(  # nosec
            str(image.resolve()).encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()

        # Save in DB
        db_entry = registry.add_review_queue_entry(
            entry_id=entry_id,
            image_path=image,
            dataset_path=inp.dataset_path,
            score=score,
            reason=reason,
            predictions=[d.model_dump() for d in detections],
        )

        queue_entries.append(
            ActiveLearningQueueItem(
                id=entry_id,
                image_path=image,
                dataset_path=inp.dataset_path,
                score=score,
                reason=reason,
                status="pending",
                predictions=detections,
                created_at=db_entry.created_at,
            )
        )

    # Sort output desc by score
    queue_entries.sort(key=lambda x: x.score, reverse=True)

    return ActiveLearningQueueRankOutput(
        ranked_count=len(queue_entries),
        queue_entries=queue_entries,
    )
