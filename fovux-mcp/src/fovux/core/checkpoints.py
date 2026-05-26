"""Shared checkpoint and metric helpers used across tools and transports."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, cast

from fovux.core.errors import FovuxCheckpointNotFoundError
from fovux.core.paths import FovuxPaths, get_fovux_home


def resolve_checkpoint(checkpoint: str) -> Path:
    """Resolve a checkpoint path or run id to a concrete file path."""
    path = Path(checkpoint)
    if path.exists():
        return path.expanduser().resolve()

    paths = FovuxPaths(get_fovux_home())
    candidates = [
        paths.runs / checkpoint / "weights" / "best.pt",
        paths.runs / checkpoint / "best.pt",
        paths.models / checkpoint,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    raise FovuxCheckpointNotFoundError(checkpoint)


def metrics_file(run_dir: Path) -> Path | None:
    """Return the preferred legacy metrics CSV path for a run, if present."""
    candidates = [run_dir / "weights" / "results.csv", run_dir / "results.csv"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def read_metric_rows(run_dir: Path) -> list[dict[str, str]]:
    """Read legacy CSV metric rows for a run."""
    results_csv = metrics_file(run_dir)
    if results_csv is None:
        return []
    try:
        rows = list(csv.DictReader(results_csv.read_text(encoding="utf-8").splitlines()))
        return cast(list[dict[str, str]], rows)
    except Exception:
        return []


def normalize_metric_row(run_id: str, row: dict[str, str]) -> dict[str, Any]:
    """Normalize a legacy CSV row into the public metric payload shape."""
    metrics: dict[str, float] = {}
    epoch_value: int | None = None
    for key, value in row.items():
        if value is None or value == "":
            continue
        try:
            numeric = float(value)
        except ValueError:
            continue
        if key == "epoch":
            epoch_value = int(numeric) + 1
        else:
            metrics[key] = numeric
    return {
        "runId": run_id,
        "epoch": epoch_value if epoch_value is not None else 0,
        "metrics": metrics,
    }


def read_metrics_summary(run_dir: Path) -> tuple[int | None, float | None]:
    """Return the latest epoch and best mAP50-like metric for a run."""
    jsonl_rows = load_metrics_jsonl(run_dir)
    if jsonl_rows:
        last = jsonl_rows[-1]
        metrics = cast(dict[str, float], last.get("metrics", {}))
        metric_key = next(
            (key for key in metrics if "map50" in key.lower() and "95" not in key.lower()),
            None,
        )
        metric_value = metrics.get(metric_key) if metric_key is not None else None
        return int(last["epoch"]), metric_value

    rows = read_metric_rows(run_dir)
    if not rows:
        return None, None
    last = rows[-1]
    epoch_raw = last.get("epoch")
    epoch = int(float(epoch_raw)) + 1 if epoch_raw is not None else len(rows)
    map50_key = next((k for k in last if "map50" in k.lower() and "95" not in k.lower()), None)
    raw_value = last.get(map50_key) if map50_key else None
    best_map50 = float(str(raw_value)) if raw_value is not None else None
    return epoch, best_map50


def load_metrics_jsonl(run_dir: Path) -> list[dict[str, Any]]:
    """Load structured metrics rows written by the training worker."""
    metrics_path = run_dir / "metrics.jsonl"
    if not metrics_path.exists():
        return []

    payloads: list[dict[str, Any]] = []
    for line in metrics_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = cast(dict[str, Any], json.loads(line))
        except json.JSONDecodeError:
            continue
        if "epoch" not in raw:
            continue
        metrics = raw.get("metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}
        payloads.append(
            {
                "runId": str(raw.get("run_id", run_dir.name)),
                "epoch": int(raw["epoch"]),
                "metrics": {
                    str(key): float(value)
                    for key, value in metrics.items()
                    if isinstance(value, (int, float))
                },
                "wall_time_s": float(raw.get("wall_time_s", 0.0) or 0.0),
                "eta_s": float(raw.get("eta_s", 0.0) or 0.0),
            }
        )
    return payloads
