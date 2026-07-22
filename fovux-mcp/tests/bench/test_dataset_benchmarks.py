"""Benchmark coverage for common dataset tools and normalized adapters."""

from __future__ import annotations

from pathlib import Path

from fovux.core.dataset_inventory import build_dataset_inventory
from fovux.schemas.dataset import DatasetFindDuplicatesInput, DatasetInspectInput
from fovux.tools.dataset_find_duplicates import _run_find_duplicates
from fovux.tools.dataset_inspect import _run_inspect


def test_dataset_inspect_benchmark(benchmark, mini_yolo_path: Path) -> None:
    """Benchmark dataset inspection on the bundled mini fixture."""
    inspect_input = DatasetInspectInput(dataset_path=mini_yolo_path, include_samples=False)
    result = benchmark(lambda: _run_inspect(inspect_input))
    assert result.total_images > 0


def test_dataset_find_duplicates_benchmark(benchmark, mini_yolo_path: Path) -> None:
    """Benchmark duplicate detection on the bundled mini fixture."""
    result = benchmark(
        lambda: _run_find_duplicates(DatasetFindDuplicatesInput(dataset_path=mini_yolo_path))
    )
    assert result.total_images > 0


def test_yolo_inventory_adapter_benchmark(benchmark, mini_yolo_path: Path) -> None:
    """Benchmark metadata-only YOLO normalization independently of image decoding."""
    result = benchmark(
        lambda: build_dataset_inventory(
            mini_yolo_path,
            "yolo",
            analyze_images=False,
            compute_fingerprints=False,
        )
    )
    assert len(result.images) == 40
    assert len(result.annotations) == 40


def test_coco_inventory_adapter_benchmark(benchmark, mini_coco_path: Path) -> None:
    """Benchmark metadata-only COCO normalization independently of image decoding."""
    result = benchmark(
        lambda: build_dataset_inventory(
            mini_coco_path,
            "coco",
            analyze_images=False,
            compute_fingerprints=False,
        )
    )
    assert len(result.images) == 20
    assert result.annotations
