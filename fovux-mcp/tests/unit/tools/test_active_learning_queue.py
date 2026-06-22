"""Tests for active learning queue tools (rank, list, submit)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PIL import Image

from fovux.core.paths import ensure_fovux_dirs
from fovux.core.runs import RunRegistry
from fovux.schemas.inference import (
    ActiveLearningQueueListInput,
    ActiveLearningQueueRankInput,
    ActiveLearningQueueSubmitInput,
    Detection,
)
from fovux.tools.active_learning_queue_list import _run_active_learning_queue_list
from fovux.tools.active_learning_queue_rank import _run_active_learning_queue_rank
from fovux.tools.active_learning_queue_submit import _run_active_learning_queue_submit


def _make_pool(root: Path) -> Path:
    pool = root / "unlabeled_pool"
    pool.mkdir(parents=True)
    Image.new("RGB", (64, 64), color=(255, 255, 255)).save(pool / "001.jpg")
    Image.new("RGB", (64, 64), color=(100, 100, 100)).save(pool / "002.jpg")
    return pool


def _make_fake_yolo_model(confs: list[float]) -> SimpleNamespace:
    return SimpleNamespace(
        predict=lambda **_kwargs: [
            SimpleNamespace(
                orig_shape=(64, 64),
                boxes=SimpleNamespace(
                    conf=SimpleNamespace(tolist=lambda: confs),
                    cls=SimpleNamespace(tolist=lambda: [0] * len(confs)),
                    xyxy=SimpleNamespace(tolist=lambda: [[10.0, 10.0, 30.0, 30.0]] * len(confs)),
                ),
                names={0: "cat"},
            )
        ]
    )


def test_active_learning_queue_rank_inserts_to_db(tmp_path: Path, monkeypatch) -> None:
    """Queue ranking should perform inference, compute scores, and persist entries in DB."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pool = _make_pool(tmp_path)
    dataset = tmp_path / "dataset"
    dataset.mkdir()

    fake_model = _make_fake_yolo_model([0.65])

    with (
        patch("fovux.tools.active_learning_queue_rank.resolve_checkpoint", return_value="ckpt.pt"),
        patch("fovux.tools.active_learning_queue_rank.load_yolo_model", return_value=fake_model),
    ):
        out = _run_active_learning_queue_rank(
            ActiveLearningQueueRankInput(
                checkpoint="ckpt.pt",
                unlabeled_pool=pool,
                dataset_path=dataset,
                strategy="entropy",
                limit=10,
            )
        )

    assert out.ranked_count == 2
    assert len(out.queue_entries) == 2
    assert out.queue_entries[0].predictions[0].class_name == "cat"
    # Entropy score = 1.0 - abs(0.65 - 0.5) * 2.0 = 1.0 - 0.3 = 0.7
    assert out.queue_entries[0].score == pytest.approx(0.7)

    # Verify SQLite DB
    paths = ensure_fovux_dirs(tmp_path)
    registry = RunRegistry(paths.runs_db)
    items = registry.list_review_queue_entries(status="pending")
    assert len(items) == 2


def test_active_learning_queue_list_retrieves_items(tmp_path: Path, monkeypatch) -> None:
    """Queue list should fetch pending entries from SQLite."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    paths = ensure_fovux_dirs(tmp_path)
    registry = RunRegistry(paths.runs_db)

    registry.add_review_queue_entry(
        entry_id="entry_abc",
        image_path=tmp_path / "img.jpg",
        dataset_path=tmp_path / "dataset",
        score=0.95,
        reason="low_confidence",
        predictions=[
            {
                "class_id": 0,
                "class_name": "cat",
                "confidence": 0.55,
                "bbox_xyxy": [0.1, 0.1, 0.2, 0.2],
            }
        ],
    )

    out = _run_active_learning_queue_list(
        ActiveLearningQueueListInput(
            dataset_path=tmp_path / "dataset",
            status="pending",
        )
    )

    assert len(out.queue_entries) == 1
    assert out.queue_entries[0].id == "entry_abc"
    assert out.queue_entries[0].predictions[0].class_name == "cat"


def test_active_learning_queue_submit_writes_labels_and_copies_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Queue submit should copy target image and generate a YOLO label file.

    It should also mark reviewed in DB.
    """
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    paths = ensure_fovux_dirs(tmp_path)
    registry = RunRegistry(paths.runs_db)

    image_file = tmp_path / "001.jpg"
    Image.new("RGB", (64, 64), color=(255, 255, 255)).save(image_file)

    dataset = tmp_path / "dataset"
    dataset.mkdir()

    registry.add_review_queue_entry(
        entry_id="entry_abc",
        image_path=image_file,
        dataset_path=dataset,
        score=0.95,
        reason="low_confidence",
        predictions=[],
    )

    corrections = [
        Detection(
            class_id=1,
            class_name="dog",
            confidence=1.0,
            bbox_xyxy=[0.1, 0.2, 0.3, 0.4],  # x_top_left, y_top_left, w, h
        )
    ]

    out = _run_active_learning_queue_submit(
        ActiveLearningQueueSubmitInput(
            entry_id="entry_abc",
            corrected_labels=corrections,
            dataset_split="train",
        )
    )

    assert out.status == "reviewed"
    assert out.copied_image_path.exists()
    assert out.written_label_path.exists()

    # Reconstruct label calculation check:
    # center_x = x + w / 2 = 0.1 + 0.3 / 2 = 0.25
    # center_y = y + h / 2 = 0.2 + 0.4 / 2 = 0.4
    # w = 0.3, h = 0.4
    label_content = out.written_label_path.read_text(encoding="utf-8").strip()
    assert label_content == "1 0.250000 0.400000 0.300000 0.400000"

    # Verify status updated to reviewed in SQLite
    db_entry = registry.get_review_queue_entry("entry_abc")
    assert db_entry is not None
    assert db_entry.status == "reviewed"


def test_active_learning_queue_rank_underrepresented_and_diversity(
    tmp_path: Path, monkeypatch
) -> None:
    """Test underrepresented class detection and diversity strategy."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pool = _make_pool(tmp_path)
    dataset = tmp_path / "dataset"
    dataset.mkdir()

    # Create existing class distribution: class 0 has 50 labels, class 1 has 1 label
    labels_dir = dataset / "labels" / "train"
    labels_dir.mkdir(parents=True)
    # 50 labels for class 0
    lines_c0 = "\n".join("0 0.5 0.5 0.2 0.2" for _ in range(50))
    (labels_dir / "existing_labels.txt").write_text(lines_c0, encoding="utf-8")
    # 1 label for class 1
    (labels_dir / "existing_labels_rare.txt").write_text("1 0.5 0.5 0.2 0.2", encoding="utf-8")

    # Predict class 1 (underrepresented class)
    fake_model = SimpleNamespace(
        predict=lambda **_kwargs: [
            SimpleNamespace(
                orig_shape=(64, 64),
                boxes=SimpleNamespace(
                    conf=SimpleNamespace(tolist=lambda: [0.9]),
                    cls=SimpleNamespace(tolist=lambda: [1]),
                    xyxy=SimpleNamespace(tolist=lambda: [[10.0, 10.0, 30.0, 30.0]]),
                ),
                names={0: "cat", 1: "dog"},
            )
        ]
    )

    with (
        patch(
            "fovux.tools.active_learning_queue_rank.resolve_checkpoint",
            return_value="ckpt.pt",
        ),
        patch(
            "fovux.tools.active_learning_queue_rank.load_yolo_model",
            return_value=fake_model,
        ),
    ):
        out = _run_active_learning_queue_rank(
            ActiveLearningQueueRankInput(
                checkpoint="ckpt.pt",
                unlabeled_pool=pool,
                dataset_path=dataset,
                strategy="diversity",
                limit=10,
            )
        )

    assert out.ranked_count == 2
    # Verify dog (class 1) is underrepresented, so reason is underrepresented_class
    assert out.queue_entries[0].reason == "underrepresented_class"
    # Diversity score should be high since class 1 has low count (1/50)
    assert out.queue_entries[0].score > 0.5


def test_active_learning_queue_rank_disagreement_and_error_likelihood(
    tmp_path: Path, monkeypatch
) -> None:
    """Test disagreement detection and error_likelihood strategy."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pool = _make_pool(tmp_path)
    dataset = tmp_path / "dataset"
    dataset.mkdir()

    # Create a weak label in the unlabeled pool that disagrees with prediction
    # Prediction will be class 0, but weak label is class 2
    (pool / "001.txt").write_text("2 0.5 0.5 0.2 0.2", encoding="utf-8")

    fake_model = SimpleNamespace(
        predict=lambda **_kwargs: [
            SimpleNamespace(
                orig_shape=(64, 64),
                boxes=SimpleNamespace(
                    conf=SimpleNamespace(tolist=lambda: [0.95]),
                    cls=SimpleNamespace(tolist=lambda: [0]),
                    xyxy=SimpleNamespace(tolist=lambda: [[10.0, 10.0, 30.0, 30.0]]),
                ),
                names={0: "cat"},
            )
        ]
    )

    with (
        patch(
            "fovux.tools.active_learning_queue_rank.resolve_checkpoint",
            return_value="ckpt.pt",
        ),
        patch(
            "fovux.tools.active_learning_queue_rank.load_yolo_model",
            return_value=fake_model,
        ),
    ):
        out = _run_active_learning_queue_rank(
            ActiveLearningQueueRankInput(
                checkpoint="ckpt.pt",
                unlabeled_pool=pool,
                dataset_path=dataset,
                strategy="error_likelihood",
                limit=1,
            )
        )

    # Only 001.jpg has the corresponding .txt label file causing disagreement
    # 001.jpg should be ranked first due to error_likelihood score = 1.0
    assert out.ranked_count == 1
    assert out.queue_entries[0].reason == "disagreement"
    assert out.queue_entries[0].score == pytest.approx(1.0)


def test_active_learning_queue_rank_outliers(tmp_path: Path, monkeypatch) -> None:
    """Test outlier detection based on box sizes and counts."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pool = _make_pool(tmp_path)
    dataset = tmp_path / "dataset"
    dataset.mkdir()

    # Case 1: Extremely tiny bounding box (area < 0.002)
    fake_model = SimpleNamespace(
        predict=lambda **_kwargs: [
            SimpleNamespace(
                orig_shape=(1000, 1000),
                boxes=SimpleNamespace(
                    conf=SimpleNamespace(tolist=lambda: [0.9]),
                    cls=SimpleNamespace(tolist=lambda: [0]),
                    xyxy=SimpleNamespace(tolist=lambda: [[10.0, 10.0, 11.0, 11.0]]),
                ),
                names={0: "cat"},
            )
        ]
    )

    with (
        patch(
            "fovux.tools.active_learning_queue_rank.resolve_checkpoint",
            return_value="ckpt.pt",
        ),
        patch(
            "fovux.tools.active_learning_queue_rank.load_yolo_model",
            return_value=fake_model,
        ),
    ):
        out = _run_active_learning_queue_rank(
            ActiveLearningQueueRankInput(
                checkpoint="ckpt.pt",
                unlabeled_pool=pool,
                dataset_path=dataset,
                strategy="least_confident",
                limit=1,
            )
        )

    assert out.ranked_count == 1
    assert out.queue_entries[0].reason == "outlier"
