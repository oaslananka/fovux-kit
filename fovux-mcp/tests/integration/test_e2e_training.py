"""Slow end-to-end training coverage."""

from __future__ import annotations

import os
import time

import pytest

from fovux.schemas.training import TrainStartInput, TrainStatusInput
from fovux.tools.train_start import _run_train_start
from fovux.tools.train_status import _run_train_status


@pytest.mark.slow
def test_e2e_training_run_completes(mini_yolo_path, tmp_fovux_home) -> None:
    """Run a real 1-epoch CPU training job when slow tests are explicitly enabled."""
    if os.environ.get("FOVUX_RUN_SLOW_TESTS") != "1":
        pytest.skip("Set FOVUX_RUN_SLOW_TESTS=1 to execute real training.")

    output = _run_train_start(
        TrainStartInput(
            dataset_path=mini_yolo_path,
            epochs=1,
            imgsz=64,
            device="cpu",
        )
    )

    deadline = time.time() + 300
    status = _run_train_status(TrainStatusInput(run_id=output.run_id))
    while status.status == "running" and time.time() < deadline:
        time.sleep(2)
        status = _run_train_status(TrainStatusInput(run_id=output.run_id))

    assert status.status in {"complete", "failed"}
    assert (output.run_path / "status.json").exists()
    if status.status == "complete":
        assert (output.run_path / "weights" / "best.pt").exists()
        assert (output.run_path / "weights" / "results.csv").exists() or (
            output.run_path / "results.csv"
        ).exists()
