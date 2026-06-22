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
                    # Let's save xyxy normalized to [0,1] or absolute
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

        # Compute uncertainty score
        if not confidences:
            score = 1.0
            reason = "no_detections"
        else:
            best = max(confidences)
            if inp.strategy == "least_confident":
                score = 1.0 - best
            elif inp.strategy == "margin" and len(confidences) > 1:
                ordered = sorted(confidences, reverse=True)
                score = 1.0 - (ordered[0] - ordered[1])
            else:  # entropy-like closeness to 0.5
                score = sum(1.0 - abs(c - 0.5) * 2.0 for c in confidences) / len(confidences)

            reason = "low_confidence" if score > 0.5 else "underrepresented_class"

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
