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


def test_split_is_reproducible_for_same_seed(tmp_path: Path) -> None:
    """A dataset split seed is reproducibility input, not a security primitive."""
    first = _run_split(
        DatasetSplitInput(
            dataset_path=FIXTURES / "mini_yolo",
            seed=2026,
            stratify_by_class=False,
            overwrite=True,
            output_path=tmp_path / "first",
        )
    )
    second = _run_split(
        DatasetSplitInput(
            dataset_path=FIXTURES / "mini_yolo",
            seed=2026,
            stratify_by_class=False,
            overwrite=True,
            output_path=tmp_path / "second",
        )
    )

    import json

    first_manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    second_manifest = json.loads(second.manifest_path.read_text(encoding="utf-8"))
    assert first_manifest == second_manifest


@pytest.mark.parametrize("relative_output", [".", "images", "labels/train", "../"])
def test_split_rejects_output_overlapping_source_dataset(
    tmp_path: Path, relative_output: str
) -> None:
    """Force-overwrite must never delete source images or annotations."""
    from shutil import copytree

    source = copytree(FIXTURES / "mini_yolo", tmp_path / "dataset")
    sentinel = source / "labels" / "train" / "000.txt"
    original = sentinel.read_bytes()
    with pytest.raises(FovuxDatasetFormatError, match="overlaps source dataset"):
        _run_split(
            DatasetSplitInput(
                dataset_path=source,
                output_path=source / relative_output,
                overwrite=True,
            )
        )
    assert sentinel.read_bytes() == original  # nosec B101 - pytest assertion
    assert (source / "data.yaml").exists()  # nosec B101 - pytest assertion


def test_split_preserves_duplicate_basenames_across_original_splits(tmp_path: Path) -> None:
    """Combining original train and val must not overwrite identically named samples."""
    output = _run_split(
        DatasetSplitInput(
            dataset_path=FIXTURES / "mini_yolo",
            ratios=(1.0, 0.0, 0.0),
            stratify_by_class=False,
            output_path=tmp_path / "combined",
        )
    )
    image_files = list((output.output_path / "images" / "train").iterdir())
    label_files = list((output.output_path / "labels" / "train").iterdir())
    assert len(image_files) == output.train_count  # nosec B101 - pytest assertion
    assert len(label_files) == output.train_count  # nosec B101 - pytest assertion
    assert {p.stem for p in image_files} == {p.stem for p in label_files}  # nosec B101 - pytest assertion


def test_write_split_retries_generated_name_collisions(tmp_path: Path) -> None:
    """A generated unique name cannot overwrite another source's original basename."""
    from fovux.tools.dataset_split import _write_yolo_split

    sources = tmp_path / "sources"
    stems = ["sample_2_1", "sample", "sample"]
    pairs = []
    for index, stem in enumerate(stems):
        parent = sources / str(index)
        parent.mkdir(parents=True)
        img = parent / f"{stem}.jpg"
        label = parent / f"{stem}.txt"
        img.write_bytes(str(index).encode())
        label.write_text(str(index), encoding="utf-8")
        pairs.append((img, label))

    dest = tmp_path / "result"
    _write_yolo_split(dest, "train", pairs)
    images = list((dest / "images" / "train").iterdir())
    labels = list((dest / "labels" / "train").iterdir())
    assert len(images) == len(pairs)  # nosec B101 - pytest assertion
    assert {path.stem for path in images} == {path.stem for path in labels}  # nosec B101 - pytest assertion
    assert {path.read_bytes() for path in images} == {b"0", b"1", b"2"}  # nosec B101 - pytest assertion
