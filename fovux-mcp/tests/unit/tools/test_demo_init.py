"""Tests for demo workspace initialization."""

from __future__ import annotations

from pathlib import Path

from fovux.schemas.management import DemoInitInput
from fovux.tools.demo_init import _run_demo_init, demo_init


def test_demo_init_creates_deterministic_workspace(tmp_fovux_home: Path) -> None:
    """demo_init should create a compact demo dataset, run, model, and export."""
    output = _run_demo_init(DemoInitInput(target_path="demo_workspace"))

    workspace = tmp_fovux_home / "demo_workspace"
    assert (workspace / "sample_dataset" / "data.yaml").exists()
    assert (workspace / "sample_dataset" / "images" / "train" / "000.jpg").exists()
    assert (workspace / "sample_dataset" / "labels" / "train" / "000.txt").exists()
    assert (tmp_fovux_home / "models" / "yolov8n.pt").exists()
    assert (tmp_fovux_home / "exports" / "demo_model.onnx").exists()
    assert output.run_id == "demo_run_01"


def test_demo_init_public_wrapper_returns_json(tmp_fovux_home: Path) -> None:
    """The public demo_init MCP wrapper should serialize the demo output."""
    payload = demo_init(target_path="demo_workspace")

    assert payload["run_id"] == "demo_run_01"
    assert payload["dataset_path"].endswith("sample_dataset")
    assert payload["model_path"].endswith("models/yolov8n.pt")
