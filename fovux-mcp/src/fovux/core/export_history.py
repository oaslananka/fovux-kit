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
    export_id = f"export_{uuid4().hex[:12]}"
    entry: dict[str, Any] = {
        "id": export_id,
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

    # Also log to SQLite database ledger if available
    try:
        from fovux.core.paths import FovuxPaths
        from fovux.core.runs import get_registry

        paths = FovuxPaths(get_fovux_home())
        registry = get_registry(paths.runs_db)

        # Try to resolve run_id from source_checkpoint
        run_id = None
        try:
            resolved_cp = source_checkpoint.resolve()
            resolved_runs = paths.runs.resolve()
            if resolved_cp.is_relative_to(resolved_runs):
                rel = resolved_cp.relative_to(resolved_runs)
                run_id = rel.parts[0]
        except Exception:  # noqa: S110
            pass

        registry.record_export(
            export_id=export_id,
            run_id=run_id,
            source_checkpoint=source_checkpoint,
            artifact_path=artifact_path,
            format=format,
            duration_s=duration_s,
            validation_result=metadata,
        )
    except Exception:  # noqa: S110
        pass

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
