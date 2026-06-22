"""active_learning_queue_list — list review queue items from the registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fovux.core.paths import ensure_fovux_dirs, get_fovux_home
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.schemas.inference import (
    ActiveLearningQueueItem,
    ActiveLearningQueueListInput,
    ActiveLearningQueueListOutput,
    Detection,
)
from fovux.server import mcp


@mcp.tool()
def active_learning_queue_list(
    dataset_path: str | None = None,
    status: str = "pending",
    limit: int = 100,
) -> dict[str, Any]:
    """Retrieve review queue items from the local SQLite index."""
    inp = ActiveLearningQueueListInput(
        dataset_path=Path(dataset_path) if dataset_path else None,
        status=status,  # type: ignore[arg-type]
        limit=limit,
    )
    with tool_event("active_learning_queue_list", status=status, limit=limit):
        output = _run_active_learning_queue_list(inp)
        return output.model_dump(mode="json")


def _run_active_learning_queue_list(
    inp: ActiveLearningQueueListInput,
) -> ActiveLearningQueueListOutput:
    paths = ensure_fovux_dirs(get_fovux_home())
    registry = get_registry(paths.runs_db)

    db_entries = registry.list_review_queue_entries(
        dataset_path=inp.dataset_path,
        status=inp.status,
        limit=inp.limit,
    )

    queue_entries: list[ActiveLearningQueueItem] = []
    for entry in db_entries:
        # Load predictions
        try:
            preds_raw = json.loads(entry.predictions_json or "[]")
            predictions = [Detection(**d) for d in preds_raw]
        except Exception:
            predictions = []

        # Load corrected labels
        corrected = None
        if entry.corrected_labels_json:
            try:
                corr_raw = json.loads(entry.corrected_labels_json)
                corrected = [Detection(**d) for d in corr_raw]
            except Exception:
                corrected = None

        queue_entries.append(
            ActiveLearningQueueItem(
                id=entry.id,
                image_path=Path(entry.image_path),
                dataset_path=Path(entry.dataset_path),
                score=entry.score,
                reason=entry.reason,
                status=entry.status,
                predictions=predictions,
                corrected_labels=corrected,
                created_at=entry.created_at,
            )
        )

    return ActiveLearningQueueListOutput(queue_entries=queue_entries)
