"""Transport-neutral run queries and metric stream orchestration."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from watchfiles import Change, awatch

from fovux.core.checkpoints import (
    load_metrics_jsonl,
    normalize_metric_row,
    read_metric_rows,
    read_metrics_summary,
)
from fovux.core.logging import get_logger
from fovux.core.runs import RunRecord, RunRegistry
from fovux.http.services.errors import ServiceError

RegistryProvider = Callable[[], RunRegistry]
DisconnectCheck = Callable[[], Awaitable[bool]]


@dataclass(frozen=True)
class RunSearchFilters:
    """Transport-neutral run search criteria."""

    query: str | None = None
    tags: tuple[str, ...] = ()
    status: tuple[str, ...] = ()
    min_map50: float | None = None
    limit: int = 50


def default_registry_provider() -> RunRegistry:
    """Return the process-wide registry while preserving runtime overrides."""
    from fovux.core import paths as path_module
    from fovux.core import runs as runs_module

    paths = path_module.ensure_fovux_dirs()
    return runs_module.get_registry(paths.runs_db)


class RunService:
    """Query run state and stream normalized metrics without a web framework."""

    def __init__(self, registry_provider: RegistryProvider = default_registry_provider) -> None:
        """Initialize the service with an injectable registry provider."""
        self._registry_provider = registry_provider

    def list_runs(self) -> list[dict[str, object]]:
        """Return summaries for all registered runs."""
        return [_run_summary(record) for record in self._registry_provider().list_runs()]

    def get_run(self, run_id: str) -> dict[str, object]:
        """Return detailed metadata for one run."""
        record = self._registry_provider().get_run(run_id)
        if record is None:
            raise ServiceError(404, f"Run {run_id} not found.")
        run_path = Path(record.run_path)
        status = str(_read_status_payload(run_path).get("status") or record.status)
        current_epoch, best_map50 = read_metrics_summary(run_path)
        return {
            "id": record.id,
            "status": status,
            "model": record.model,
            "dataset_path": record.dataset_path,
            "task": record.task,
            "epochs": record.epochs,
            "pid": record.pid,
            "run_path": record.run_path,
            "current_epoch": current_epoch,
            "best_map50": best_map50,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "started_at": record.started_at.isoformat() if record.started_at else None,
            "finished_at": record.finished_at.isoformat() if record.finished_at else None,
            "tags": _decode_tags(record.tags_json),
        }

    def search_runs(self, filters: RunSearchFilters) -> list[dict[str, object]]:
        """Search runs by text, tags, status, and minimum mAP50."""
        records = self._registry_provider().list_runs(limit=max(filters.limit, 1) * 4)
        matched: list[dict[str, object]] = []
        lowered_query = filters.query.lower() if filters.query else None
        required_statuses = {status.lower() for status in filters.status}
        required_tags = {tag.lower() for tag in filters.tags}

        for record in records:
            record_tags = {tag.lower() for tag in _decode_tags(record.tags_json)}
            haystack = _run_search_haystack(record, record_tags)
            if lowered_query and lowered_query not in haystack:
                continue
            if required_statuses and str(record.status).lower() not in required_statuses:
                continue
            if required_tags and not required_tags.issubset(record_tags):
                continue
            _, best_map50 = read_metrics_summary(Path(record.run_path))
            if filters.min_map50 is not None and (
                best_map50 is None or best_map50 < filters.min_map50
            ):
                continue
            matched.append(_search_result(record, record_tags, best_map50))
            if len(matched) >= filters.limit:
                break
        return matched

    def resolve_run_dir(self, run_id: str) -> Path:
        """Resolve a registered run directory or raise a typed 404 error."""
        record = self._registry_provider().get_run(run_id)
        if record is None:
            raise ServiceError(404, f"Run {run_id} not found.")
        return Path(record.run_path)

    def load_metric_payloads(self, run_id: str, run_dir: Path) -> list[dict[str, object]]:
        """Load the canonical metric snapshot for a run."""
        return _load_metric_payloads(run_id, run_dir)

    def load_metrics_jsonl(self, run_id: str, run_dir: Path) -> list[dict[str, object]]:
        """Load raw normalized metrics.jsonl payloads."""
        return _load_metrics_jsonl(run_id, run_dir)

    def load_metric_payload_delta(
        self,
        run_id: str,
        run_dir: Path,
        emitted_count: int,
        previous_offset: int,
    ) -> tuple[int, int, list[dict[str, object]]]:
        """Load metrics appended after a previous byte offset."""
        return _load_metric_payload_delta(run_id, run_dir, emitted_count, previous_offset)

    def metric_event_stream(
        self,
        *,
        run_id: str,
        run_dir: Path,
        disconnect_check: DisconnectCheck,
        shutdown_event: asyncio.Event,
    ) -> AsyncIterator[str]:
        """Return the canonical SSE metric event iterator."""
        return _metric_event_stream(
            run_id=run_id,
            run_dir=run_dir,
            disconnect_check=disconnect_check,
            shutdown_event=shutdown_event,
        )


def _run_summary(record: RunRecord) -> dict[str, object]:
    run_path = Path(str(record.run_path))
    status = str(_read_status_payload(run_path).get("status") or record.status)
    current_epoch, best_map50 = read_metrics_summary(run_path)
    return {
        "id": str(record.id),
        "status": status,
        "model": str(record.model),
        "epochs": int(record.epochs),
        "run_path": str(record.run_path),
        "current_epoch": current_epoch,
        "best_map50": best_map50,
        "created_at": record.created_at.isoformat() if record.created_at else None,
    }


def _read_status_payload(run_dir: Path) -> dict[str, object]:
    status_file = run_dir / "status.json"
    if not status_file.exists():
        return {}
    try:
        payload = json.loads(status_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return cast(dict[str, object], payload) if isinstance(payload, dict) else {}


def _decode_tags(value: object) -> list[str]:
    try:
        decoded = json.loads(str(value or "[]"))
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(decoded, list):
        return []
    return [str(tag) for tag in decoded]


def _run_search_haystack(record: RunRecord, tags: set[str]) -> str:
    return " ".join(
        [
            str(record.id),
            str(record.model),
            str(record.dataset_path),
            str(record.task),
            " ".join(tags),
            str(record.extra_json or ""),
        ]
    ).lower()


def _search_result(
    record: RunRecord,
    tags: set[str],
    best_map50: float | None,
) -> dict[str, object]:
    return {
        "id": record.id,
        "status": record.status,
        "model": record.model,
        "dataset_path": record.dataset_path,
        "task": record.task,
        "epochs": record.epochs,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "best_map50": best_map50,
        "tags": sorted(tags),
    }


async def _metric_event_stream(
    *,
    run_id: str,
    run_dir: Path,
    disconnect_check: DisconnectCheck,
    shutdown_event: asyncio.Event,
) -> AsyncIterator[str]:
    yield "retry: 5000\n\n"
    metrics_jsonl = run_dir / "metrics.jsonl"
    snapshot = _load_metric_payloads(run_id, run_dir)
    for payload in snapshot:
        yield f"event: metric\ndata: {json.dumps(payload)}\n\n"
    emitted_count = len(snapshot)
    jsonl_offset = metrics_jsonl.stat().st_size if metrics_jsonl.exists() else 0
    if _is_terminal_run(run_dir):
        yield "event: done\ndata: {}\n\n"
        return

    watcher = awatch(run_dir, stop_event=shutdown_event, debounce=150)
    last_heartbeat = time.monotonic()
    while not shutdown_event.is_set():
        if await disconnect_check():
            get_logger(__name__).info("metrics_stream_disconnected", run_id=run_id)
            break
        try:
            changes = await asyncio.wait_for(watcher.__anext__(), timeout=15.0)
        except TimeoutError:
            yield ": keep-alive\n\n"
            last_heartbeat = time.monotonic()
            continue
        except StopAsyncIteration:
            break
        if _contains_metrics_jsonl_change(changes):
            emitted_count, jsonl_offset, delta_payloads = _load_metric_payload_delta(
                run_id, run_dir, emitted_count, jsonl_offset
            )
        else:
            delta_payloads = _load_metric_payloads(run_id, run_dir)[emitted_count:]
            emitted_count += len(delta_payloads)
        for payload in delta_payloads:
            yield f"event: metric\ndata: {json.dumps(payload)}\n\n"
            last_heartbeat = time.monotonic()
        if _is_terminal_run(run_dir):
            yield "event: done\ndata: {}\n\n"
            break
        if time.monotonic() - last_heartbeat >= 15.0:
            yield ": keep-alive\n\n"
            last_heartbeat = time.monotonic()


def _load_metric_payloads(run_id: str, run_dir: Path) -> list[dict[str, object]]:
    payloads = load_metrics_jsonl(run_dir)
    if payloads:
        return payloads
    return [normalize_metric_row(run_id, row) for row in read_metric_rows(run_dir)]


def _load_metrics_jsonl(run_id: str, run_dir: Path) -> list[dict[str, object]]:
    del run_id
    return load_metrics_jsonl(run_dir)


def _contains_metrics_jsonl_change(changes: set[tuple[Change, str]]) -> bool:
    return any(Path(changed_path).name == "metrics.jsonl" for _, changed_path in changes)


def _load_metric_payload_delta(
    run_id: str,
    run_dir: Path,
    emitted_count: int,
    previous_offset: int,
) -> tuple[int, int, list[dict[str, object]]]:
    metrics_path = run_dir / "metrics.jsonl"
    if not metrics_path.exists():
        full_payloads = _load_metric_payloads(run_id, run_dir)
        new_payloads = full_payloads[emitted_count:]
        return emitted_count + len(new_payloads), previous_offset, new_payloads
    current_size = metrics_path.stat().st_size
    if current_size < previous_offset:
        refreshed = load_metrics_jsonl(run_dir)
        return len(refreshed), current_size, refreshed
    if current_size == previous_offset:
        return emitted_count, previous_offset, []

    with metrics_path.open("r", encoding="utf-8") as handle:
        handle.seek(previous_offset)
        lines = handle.read().splitlines()
    delta_payloads = [
        _normalize_delta_line(line, run_id, emitted_count, index)
        for index, line in enumerate(lines)
    ]
    filtered = [payload for payload in delta_payloads if payload is not None]
    return emitted_count + len(filtered), current_size, filtered


def _normalize_delta_line(
    line: str,
    run_id: str,
    emitted_count: int,
    index: int,
) -> dict[str, object] | None:
    if not line.strip():
        return None
    try:
        raw = cast(dict[str, object], json.loads(line))
    except json.JSONDecodeError:
        return None
    metrics = raw.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    epoch_value = raw.get("epoch", emitted_count + index + 1)
    return {
        "runId": str(raw.get("run_id", run_id)),
        "epoch": int(epoch_value) if isinstance(epoch_value, int | float | str) else 0,
        "metrics": {
            str(key): float(value)
            for key, value in metrics.items()
            if isinstance(value, int | float)
        },
    }


def _is_terminal_run(run_dir: Path) -> bool:
    status = str(_read_status_payload(run_dir).get("status", "")).lower()
    return status in {"complete", "completed", "failed", "stopped"}
