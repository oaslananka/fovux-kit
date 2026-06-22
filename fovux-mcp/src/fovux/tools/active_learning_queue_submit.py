"""active_learning_queue_submit — apply review corrections to a dataset."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fovux.core.paths import ensure_fovux_dirs, get_fovux_home
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.schemas.inference import (
    ActiveLearningQueueSubmitInput,
    ActiveLearningQueueSubmitOutput,
)
from fovux.server import mcp


@mcp.tool()
def active_learning_queue_submit(
    entry_id: str,
    corrected_labels: list[dict[str, Any]],
    dataset_split: str = "train",
) -> dict[str, Any]:
    """Submit label corrections for an image and save it into the target dataset split."""
    from fovux.schemas.inference import Detection

    inp = ActiveLearningQueueSubmitInput(
        entry_id=entry_id,
        corrected_labels=[Detection(**d) for d in corrected_labels],
        dataset_split=dataset_split,  # type: ignore[arg-type]
    )
    with tool_event("active_learning_queue_submit", entry_id=entry_id, split=dataset_split):
        output = _run_active_learning_queue_submit(inp)
        return output.model_dump(mode="json")


def _run_active_learning_queue_submit(
    inp: ActiveLearningQueueSubmitInput,
) -> ActiveLearningQueueSubmitOutput:
    paths = ensure_fovux_dirs(get_fovux_home())
    registry = get_registry(paths.runs_db)

    # 1. Fetch entry
    entry = registry.get_review_queue_entry(inp.entry_id)
    if entry is None:
        raise ValueError(f"Review queue entry '{inp.entry_id}' not found.")

    image_src = Path(entry.image_path)
    if not image_src.exists():
        raise FileNotFoundError(f"Source image '{image_src}' does not exist.")

    # 2. Resolve dataset paths
    dataset_path = Path(entry.dataset_path)
    images_dir = dataset_path / "images" / inp.dataset_split
    labels_dir = dataset_path / "labels" / inp.dataset_split

    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    image_dst = images_dir / image_src.name
    label_dst = labels_dir / f"{image_src.stem}.txt"

    # 3. Copy image
    shutil.copy2(image_src, image_dst)

    # 4. Generate YOLO labels
    lines: list[str] = []
    for det in inp.corrected_labels:
        if len(det.bbox_xyxy) < 4:
            continue
        # bbox_xyxy stores [x_top_left, y_top_left, width, height]
        x, y, w, h = det.bbox_xyxy[:4]
        center_x = x + w / 2
        center_y = y + h / 2
        lines.append(f"{det.class_id} {center_x:.6f} {center_y:.6f} {w:.6f} {h:.6f}")

    label_dst.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    # 5. Mark as reviewed in DB
    registry.update_review_queue_status(
        entry_id=inp.entry_id,
        status="reviewed",
        corrected_labels=[d.model_dump() for d in inp.corrected_labels],
    )

    return ActiveLearningQueueSubmitOutput(
        entry_id=inp.entry_id,
        status="reviewed",
        copied_image_path=image_dst,
        written_label_path=label_dst,
    )
