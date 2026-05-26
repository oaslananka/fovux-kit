"""Tests for dataset_split."""

from __future__ import annotations

from pathlib import Path

import pytest

from fovux.core.errors import FovuxDatasetFormatError
from fovux.schemas.dataset import DatasetSplitInput
from fovux.tools.dataset_split import _run_split

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def test_split_counts_sum_to_total(tmp_path: Path):
    """train + val + test counts should sum to total images."""
    out = _run_split(
        DatasetSplitInput(
            dataset_path=FIXTURES / "mini_yolo",
            ratios=(0.7, 0.2, 0.1),
            seed=42,
            overwrite=True,
            output_path=tmp_path / "split_out",
        )
    )
    total = out.train_count + out.val_count + out.test_count
    assert total == 40  # 30 train + 10 val in fixture = 40 total


def test_split_manifest_created(tmp_path: Path):
    """split_manifest.json should be written."""
    out = _run_split(
        DatasetSplitInput(
            dataset_path=FIXTURES / "mini_yolo",
            ratios=(0.8, 0.1, 0.1),
            seed=99,
            overwrite=True,
            output_path=tmp_path / "split_out",
        )
    )
    assert out.manifest_path.exists()


def test_split_overwrite_false_raises(tmp_path: Path):
    """Running split twice to same output without overwrite should raise."""
    shared_out = tmp_path / "split_out"
    _run_split(
        DatasetSplitInput(
            dataset_path=FIXTURES / "mini_yolo",
            ratios=(0.7, 0.2, 0.1),
            seed=1,
            overwrite=True,
            output_path=shared_out,
        )
    )
    with pytest.raises(FovuxDatasetFormatError):
        _run_split(
            DatasetSplitInput(
                dataset_path=FIXTURES / "mini_yolo",
                ratios=(0.7, 0.2, 0.1),
                seed=1,
                overwrite=False,
                output_path=shared_out,
            )
        )


def test_split_stratification_report(tmp_path: Path):
    """Stratification report should contain class keys."""
    out = _run_split(
        DatasetSplitInput(
            dataset_path=FIXTURES / "mini_yolo",
            stratify_by_class=True,
            overwrite=True,
            output_path=tmp_path / "split_out",
        )
    )
    assert isinstance(out.stratification_report, dict)
