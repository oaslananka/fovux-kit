"""active_learning_select — rank unlabeled images for annotation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.errors import FovuxDatasetNotFoundError
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.schemas.inference import ActiveLearningSelectInput, ActiveLearningSelectOutput
from fovux.server import mcp


@mcp.tool()
def active_learning_select(
    checkpoint: str,
    unlabeled_pool: str,
    strategy: str = "entropy",
    budget: int = 100,
    imgsz: int = 640,
    conf: float = 0.25,
    device: str = "auto",
) -> dict[str, Any]:
    """Select the most uncertain images from an unlabeled pool."""
    inp = ActiveLearningSelectInput(
        checkpoint=checkpoint,
        unlabeled_pool=Path(unlabeled_pool),
        strategy=strategy,  # type: ignore[arg-type]
        budget=budget,
        imgsz=imgsz,
        conf=conf,
        device=device,
    )
    with tool_event("active_learning_select", checkpoint=checkpoint, unlabeled_pool=unlabeled_pool):
        return _run_active_learning_select(inp).model_dump(mode="json")


def _run_active_learning_select(inp: ActiveLearningSelectInput) -> ActiveLearningSelectOutput:
    pool = inp.unlabeled_pool.expanduser().resolve()
    if not pool.exists():
        raise FovuxDatasetNotFoundError(str(pool))
    images = _find_images(pool)
    scored = [
        {
            "image_path": str(image),
            "score": _score_image(inp.checkpoint, image, inp.strategy),
            "strategy": inp.strategy,
        }
        for image in images
    ]
    selected = sorted(scored, key=lambda item: cast(float, item["score"]), reverse=True)[
        : max(inp.budget, 0)
    ]
    return ActiveLearningSelectOutput(
        checkpoint=inp.checkpoint,
        strategy=inp.strategy,
        budget=inp.budget,
        selected=selected,
    )


def _score_image(checkpoint: str, image_path: Path, strategy: str) -> float:
    model = load_yolo_model(resolve_checkpoint(checkpoint))
    result = model.predict(source=str(image_path), verbose=False)[0]
    confidences = _extract_confidences(result)
    if not confidences:
        return 1.0
    best = max(confidences)
    if strategy == "least_confident":
        return 1.0 - best
    if strategy == "margin" and len(confidences) > 1:
        ordered = sorted(confidences, reverse=True)
        return 1.0 - (ordered[0] - ordered[1])
    return sum(1.0 - abs(confidence - 0.5) * 2.0 for confidence in confidences) / len(confidences)


def _extract_confidences(result: object) -> list[float]:
    boxes = getattr(result, "boxes", None)
    conf = getattr(boxes, "conf", None)
    if conf is None:
        return []
    if hasattr(conf, "tolist"):
        return [float(value) for value in conf.tolist()]
    return [float(value) for value in conf]


def _find_images(root: Path) -> list[Path]:
    image_exts = {".jpg", ".jpeg", ".png", ".bmp"}
    return sorted(path for path in root.rglob("*") if path.suffix.lower() in image_exts)
