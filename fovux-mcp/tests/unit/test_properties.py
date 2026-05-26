"""Property-based tests for core invariants."""

from __future__ import annotations

from pathlib import Path

import imagehash
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from PIL import Image

from fovux.core.dataset_utils import parse_yolo_label
from fovux.schemas.dataset import DatasetSplitInput
from fovux.tools.dataset_split import _run_split


def _write_tiny_dataset(root: Path, total_images: int) -> None:
    (root / "images").mkdir(parents=True, exist_ok=True)
    (root / "labels").mkdir(parents=True, exist_ok=True)
    for index in range(total_images):
        Image.new("RGB", (8, 8), color=(index % 255, 10, 10)).save(root / "images" / f"{index}.png")
        (root / "labels" / f"{index}.txt").write_text("0 0.500000 0.500000 0.250000 0.250000\n")
    (root / "data.yaml").write_text("path: .\ntrain: images\nval: images\nnc: 1\nnames: ['item']\n")


@settings(
    max_examples=8,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    total_images=st.integers(min_value=3, max_value=12),
    train_ratio=st.floats(min_value=0.5, max_value=0.8),
    val_ratio=st.floats(min_value=0.1, max_value=0.3),
)
def test_dataset_split_counts_sum_to_total(
    tmp_path: Path,
    total_images: int,
    train_ratio: float,
    val_ratio: float,
) -> None:
    """Generated splits should account for every input image."""
    test_ratio = max(0.05, 1.0 - train_ratio - val_ratio)
    ratios_total = train_ratio + val_ratio + test_ratio
    train_ratio /= ratios_total
    val_ratio /= ratios_total
    test_ratio /= ratios_total

    ratio_suffix = f"{total_images}_{int(train_ratio * 1000)}_{int(val_ratio * 1000)}"
    dataset_root = tmp_path / f"dataset_{ratio_suffix}"
    _write_tiny_dataset(dataset_root, total_images)
    split_output = tmp_path / f"split_out_{ratio_suffix}"

    result = _run_split(
        DatasetSplitInput(
            dataset_path=dataset_root,
            ratios=(train_ratio, val_ratio, test_ratio),
            output_path=split_output,
            overwrite=True,
        )
    )

    assert result.train_count + result.val_count + result.test_count == total_images


@settings(
    max_examples=12,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    cls=st.integers(min_value=0, max_value=4),
    cx=st.integers(min_value=0, max_value=1000),
    cy=st.integers(min_value=0, max_value=1000),
    w=st.integers(min_value=1, max_value=1000),
    h=st.integers(min_value=1, max_value=1000),
)
def test_yolo_label_round_trip(
    tmp_path: Path,
    cls: int,
    cx: int,
    cy: int,
    w: int,
    h: int,
) -> None:
    """Parsing a serialized YOLO row should preserve the numeric tuple."""
    values = [cx / 1000, cy / 1000, w / 1000, h / 1000]
    label_file = tmp_path / "sample.txt"
    label_file.write_text(f"{cls} " + " ".join(f"{value:.6f}" for value in values) + "\n")

    parsed = parse_yolo_label(label_file)
    assert parsed == [(cls, *values)]


@settings(
    max_examples=8,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(pixel=st.integers(min_value=0, max_value=255))
def test_phash_distance_is_symmetric_and_zero_for_identical_images(
    tmp_path: Path,
    pixel: int,
) -> None:
    """Perceptual hash distance should be symmetric and zero for identical images."""
    image_a = Image.new("RGB", (16, 16), color=(pixel, pixel, pixel))
    image_b = Image.new("RGB", (16, 16), color=(pixel, pixel, pixel))

    hash_a = imagehash.phash(image_a)
    hash_b = imagehash.phash(image_b)

    assert hash_a - hash_b == hash_b - hash_a
    assert hash_a - hash_b == 0
