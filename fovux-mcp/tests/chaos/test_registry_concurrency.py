"""Chaos tests for concurrent registry writes."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from fovux.core.runs import RunRegistry


@pytest.mark.chaos
def test_registry_handles_concurrent_run_writes(tmp_path: Path) -> None:
    """Parallel writers should not corrupt the SQLite run registry."""
    registry = RunRegistry(tmp_path / "runs.db")

    def write_run(index: int) -> str:
        run_id = f"run_{index:03d}"
        registry.create_run(
            run_id=run_id,
            run_path=tmp_path / "runs" / run_id,
            model="yolov8n.pt",
            dataset_path=tmp_path / "dataset",
            task="detect",
            epochs=1,
            tags=[],
        )
        registry.update_status(run_id, "running", pid=index)
        return run_id

    with ThreadPoolExecutor(max_workers=8) as pool:
        run_ids = list(pool.map(write_run, range(20)))

    records = registry.list_runs()
    assert len({record.id for record in records}) == 20
    assert set(run_ids) == {record.id for record in records}
