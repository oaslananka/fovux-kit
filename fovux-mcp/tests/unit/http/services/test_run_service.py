"""Service-level tests for run queries and metric streams."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from fovux.core.runs import RunRegistry
from fovux.http.services.errors import ServiceError
from fovux.http.services.runs import RunSearchFilters, RunService


def _seed_registry(tmp_path: Path) -> tuple[RunRegistry, Path]:
    registry = RunRegistry(tmp_path / "runs.db")
    run_dir = tmp_path / "runs" / "run_service"
    run_dir.mkdir(parents=True)
    registry.create_run(
        run_id="run_service",
        run_path=run_dir,
        model="yolov8n.pt",
        dataset_path=tmp_path / "dataset",
        task="detect",
        epochs=3,
        tags=["edge", "nightly"],
    )
    registry.update_status("run_service", "running", pid=123)
    return registry, run_dir


def test_run_service_uses_status_file_and_metric_summary(tmp_path: Path) -> None:
    registry, run_dir = _seed_registry(tmp_path)
    (run_dir / "status.json").write_text('{"status":"completed"}', encoding="utf-8")
    (run_dir / "metrics.jsonl").write_text(
        '{"run_id":"run_service","epoch":2,"metrics":{"metrics/mAP50(B)":0.61}}\n',
        encoding="utf-8",
    )
    service = RunService(registry_provider=lambda: registry)

    summary = service.list_runs()[0]
    detail = service.get_run("run_service")

    assert summary["status"] == "completed"
    assert summary["current_epoch"] == 2
    assert summary["best_map50"] == pytest.approx(0.61)
    assert detail["tags"] == ["edge", "nightly"]
    assert detail["pid"] == 123


def test_run_service_searches_without_http_transport(tmp_path: Path) -> None:
    registry, _run_dir = _seed_registry(tmp_path)
    service = RunService(registry_provider=lambda: registry)

    matched = service.search_runs(
        RunSearchFilters(query="yolov8", tags=("edge",), status=("running",), limit=5)
    )
    missing = service.search_runs(RunSearchFilters(query="absent"))

    assert [item["id"] for item in matched] == ["run_service"]
    assert matched[0]["tags"] == ["edge", "nightly"]
    assert missing == []


def test_run_service_missing_run_is_typed_error(tmp_path: Path) -> None:
    registry = RunRegistry(tmp_path / "runs.db")
    service = RunService(registry_provider=lambda: registry)

    with pytest.raises(ServiceError) as exc_info:
        service.get_run("missing")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Run missing not found."


def test_run_service_metric_delta_and_terminal_stream(tmp_path: Path) -> None:
    registry, run_dir = _seed_registry(tmp_path)
    metrics = run_dir / "metrics.jsonl"
    metrics.write_text(
        '{"run_id":"run_service","epoch":1,"metrics":{"loss":1.0}}\n',
        encoding="utf-8",
    )
    service = RunService(registry_provider=lambda: registry)
    offset = metrics.stat().st_size
    with metrics.open("a", encoding="utf-8") as handle:
        handle.write('{"run_id":"run_service","epoch":2,"metrics":{"loss":0.5}}\n')

    count, new_offset, payloads = service.load_metric_payload_delta(
        "run_service", run_dir, emitted_count=1, previous_offset=offset
    )
    (run_dir / "status.json").write_text('{"status":"completed"}', encoding="utf-8")

    async def disconnected() -> bool:
        return False

    async def collect() -> list[str]:
        stream = service.metric_event_stream(
            run_id="run_service",
            run_dir=run_dir,
            disconnect_check=disconnected,
            shutdown_event=asyncio.Event(),
        )
        return [event async for event in stream]

    events = asyncio.run(collect())

    assert count == 2
    assert new_offset == metrics.stat().st_size
    assert payloads == [{"runId": "run_service", "epoch": 2, "metrics": {"loss": 0.5}}]
    assert events[0] == "retry: 5000\n\n"
    assert json.loads(events[1].split("data: ", 1)[1])["epoch"] == 1
    assert events[-1] == "event: done\ndata: {}\n\n"
