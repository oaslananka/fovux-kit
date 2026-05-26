"""Append-only export history helpers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fovux.core.paths import get_fovux_home


def exports_history_path() -> Path:
    """Return the global exports history JSONL path."""
    return get_fovux_home() / "exports.jsonl"


def record_export_history(
    *,
    source_checkpoint: Path,
    artifact_path: Path,
    format: str,
    duration_s: float,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one export or quantization history entry."""
    entry: dict[str, Any] = {
        "id": f"export_{uuid4().hex[:12]}",
        "source_checkpoint": str(source_checkpoint),
        "artifact_path": str(artifact_path),
        "format": format,
        "duration_s": round(duration_s, 6),
        "created_at": datetime.now(UTC).isoformat(),
    }
    if metadata:
        entry.update(metadata)

    path = exports_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def read_export_history(limit: int = 200) -> list[dict[str, Any]]:
    """Read recent export history entries."""
    path = exports_history_path()
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict):
            entries.append(raw)
    return entries[-limit:]
