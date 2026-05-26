"""Tests for roadmap tools added after the v2.0 stabilization surface."""

from __future__ import annotations

import json
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PIL import Image

from fovux.core.errors import FovuxDatasetNotFoundError, FovuxError, FovuxTrainingRunNotFoundError
from fovux.core.paths import ensure_fovux_dirs
from fovux.core.runs import RunRegistry
from fovux.core.tool_registry import available_tools
from fovux.schemas.dataset import DatasetAugmentInput
from fovux.schemas.inference import (
    ActiveLearningSelectInput,
    DistillModelInput,
    InferEnsembleInput,
    ModelCompareVisualInput,
    TrainAdjustInput,
)
from fovux.schemas.management import RunArchiveInput
from fovux.tools.active_learning_select import (
    _extract_confidences,
    _run_active_learning_select,
    _score_image,
)
from fovux.tools.dataset_augment import _run_dataset_augment
from fovux.tools.distill_model import _run_distill_model
from fovux.tools.infer_ensemble import _run_infer_ensemble
from fovux.tools.model_compare_visual import _run_model_compare_visual
from fovux.tools.run_archive import _run_run_archive
from fovux.tools.sync_to_mlflow import _run_sync_to_mlflow
from fovux.tools.train_adjust import _run_train_adjust


def _seed_complete_run(home: Path, run_id: str = "run_archive_me") -> Path:
    paths = ensure_fovux_dirs(home)
    run_dir = paths.runs / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "status.json").write_text('{"status": "complete"}', encoding="utf-8")
    (run_dir / "artifact.txt").write_text("payload", encoding="utf-8")
    registry = RunRegistry(paths.runs_db)
    registry.create_run(
        run_id=run_id,
        run_path=run_dir,
        model="yolov8n.pt",
        dataset_path=home / "dataset",
        task="detect",
        epochs=1,
    )
    registry.update_status(run_id, "complete")
    return run_dir


def _make_yolo_dataset(root: Path) -> Path:
    images = root / "images" / "train"
    labels = root / "labels" / "train"
    images.mkdir(parents=True)
    labels.mkdir(parents=True)
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(images / "sample.jpg")
    (labels / "sample.txt").write_text("0 0.250000 0.500000 0.200000 0.300000\n")
    (root / "data.yaml").write_text(
        "path: .\ntrain: images/train\nnames: [thing]\n",
        encoding="utf-8",
    )
    return root


def test_tool_registry_includes_new_roadmap_tools() -> None:
    """The HTTP and MCP registry should expose the new roadmap tools."""
    expected = {
        "active_learning_select",
        "dataset_augment",
        "distill_model",
        "infer_ensemble",
        "model_compare_visual",
        "run_archive",
        "sync_to_mlflow",
        "train_adjust",
    }
    assert expected.issubset(set(available_tools()))


def test_run_archive_moves_completed_run_to_archive(tmp_path: Path, monkeypatch) -> None:
    """Completed runs should be tarred under FOVUX_HOME/archive and marked archived."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    run_dir = _seed_complete_run(tmp_path)

    output = _run_run_archive(RunArchiveInput(run_id=run_dir.name))

    assert output.archive_path.exists()
    assert not run_dir.exists()
    with tarfile.open(output.archive_path, "r:gz") as archive:
        assert f"{run_dir.name}/artifact.txt" in archive.getnames()
    record = RunRegistry(ensure_fovux_dirs(tmp_path).runs_db).get_run(run_dir.name)
    assert record is not None
    assert record.status == "archived"
    assert json.loads(record.extra_json)["archive_path"] == str(output.archive_path)


def test_dataset_augment_horizontal_flip_updates_yolo_label(tmp_path: Path) -> None:
    """Horizontal flips should mirror YOLO center-x coordinates."""
    dataset = _make_yolo_dataset(tmp_path / "dataset")
    output_dir = tmp_path / "augmented"

    output = _run_dataset_augment(
        DatasetAugmentInput(
            dataset_path=dataset,
            techniques=["flip_h"],
            multiplier=1,
            output_path=output_dir,
        )
    )

    assert output.generated_images == 1
    label = (output_dir / "labels" / "train" / "sample_aug0.txt").read_text(encoding="utf-8")
    assert label.startswith("0 0.750000 0.500000")


def test_model_compare_visual_writes_side_by_side_image(tmp_path: Path) -> None:
    """Visual comparison should save a concrete PNG artifact."""
    image_path = tmp_path / "frame.jpg"
    Image.new("RGB", (20, 20), color=(255, 255, 255)).save(image_path)
    output_path = tmp_path / "comparison.png"

    with patch(
        "fovux.tools.model_compare_visual._predict_detections",
        return_value=[{"class_name": "thing", "confidence": 0.9, "bbox_xyxy": [1, 2, 10, 12]}],
    ):
        output = _run_model_compare_visual(
            ModelCompareVisualInput(
                checkpoint_a="a.pt",
                checkpoint_b="b.pt",
                image_path=image_path,
                output_path=output_path,
            )
        )

    assert output.output_path == output_path
    assert output.output_path.exists()


def test_infer_ensemble_returns_fused_detections(tmp_path: Path) -> None:
    """Ensemble inference should aggregate detections from multiple checkpoints."""
    image_path = tmp_path / "frame.jpg"
    Image.new("RGB", (20, 20), color=(255, 255, 255)).save(image_path)
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"weights")

    with patch(
        "fovux.tools.infer_ensemble._predict_checkpoint",
        return_value=[
            {"class_id": 0, "class_name": "thing", "confidence": 0.9, "bbox_xyxy": [1, 1, 8, 8]}
        ],
    ):
        output = _run_infer_ensemble(
            InferEnsembleInput(
                checkpoints=[str(checkpoint), str(checkpoint)], image_path=image_path
            )
        )

    assert output.detection_count == 1
    assert output.detections[0]["class_name"] == "thing"


def test_active_learning_select_picks_highest_uncertainty(tmp_path: Path) -> None:
    """Active learning should rank unlabeled images by uncertainty score."""
    pool = tmp_path / "pool"
    pool.mkdir()
    for name in ("low.jpg", "high.jpg"):
        Image.new("RGB", (8, 8), color=(255, 255, 255)).save(pool / name)
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"weights")

    def fake_uncertainty(_checkpoint: str, image: Path, _strategy: str) -> float:
        return 0.9 if image.name == "high.jpg" else 0.1

    with patch("fovux.tools.active_learning_select._score_image", side_effect=fake_uncertainty):
        output = _run_active_learning_select(
            ActiveLearningSelectInput(checkpoint=str(checkpoint), unlabeled_pool=pool, budget=1)
        )

    assert output.selected[0]["image_path"] == str(pool / "high.jpg")


def test_active_learning_select_rejects_missing_pool(tmp_path: Path) -> None:
    """Active learning should fail clearly for missing unlabeled image pools."""
    with pytest.raises(FovuxDatasetNotFoundError):
        _run_active_learning_select(
            ActiveLearningSelectInput(
                checkpoint=str(tmp_path / "model.pt"),
                unlabeled_pool=tmp_path / "missing",
            )
        )


def test_active_learning_score_strategies(tmp_path: Path) -> None:
    """Uncertainty scoring should cover least-confident, margin, entropy, and no boxes."""
    checkpoint = tmp_path / "model.pt"
    checkpoint.write_bytes(b"weights")
    image = tmp_path / "image.jpg"
    Image.new("RGB", (8, 8), color=(255, 255, 255)).save(image)

    def fake_model(confidences: list[float]) -> SimpleNamespace:
        return SimpleNamespace(
            predict=lambda **_kwargs: [
                SimpleNamespace(
                    boxes=SimpleNamespace(conf=SimpleNamespace(tolist=lambda: confidences))
                )
            ]
        )

    with (
        patch("fovux.tools.active_learning_select.resolve_checkpoint", return_value=checkpoint),
        patch("fovux.tools.active_learning_select.load_yolo_model", return_value=fake_model([])),
    ):
        assert _score_image(str(checkpoint), image, "entropy") == 1.0

    with (
        patch("fovux.tools.active_learning_select.resolve_checkpoint", return_value=checkpoint),
        patch(
            "fovux.tools.active_learning_select.load_yolo_model",
            return_value=fake_model([0.8, 0.55]),
        ),
    ):
        assert _score_image(str(checkpoint), image, "least_confident") == pytest.approx(0.2)
        assert _score_image(str(checkpoint), image, "margin") == pytest.approx(0.75)
        assert _score_image(str(checkpoint), image, "entropy") == pytest.approx(0.65)


def test_extract_confidences_handles_iterables_and_missing_boxes() -> None:
    """Confidence extraction should accept tensor-like and iterable confidence collections."""
    assert _extract_confidences(SimpleNamespace(boxes=None)) == []
    assert _extract_confidences(SimpleNamespace(boxes=SimpleNamespace(conf=[0.1, 0.9]))) == [
        0.1,
        0.9,
    ]


def test_distill_model_starts_training_with_distillation_args(tmp_path: Path, monkeypatch) -> None:
    """Distillation should delegate to train_start with teacher metadata."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    dataset = _make_yolo_dataset(tmp_path / "dataset")
    teacher = tmp_path / "teacher.pt"
    teacher.write_bytes(b"weights")

    with patch("fovux.tools.distill_model._run_train_start") as start:
        start.return_value = SimpleNamespace(
            run_id="distill_run",
            status="running",
            pid=123,
            run_path=tmp_path / "runs" / "distill_run",
            model_dump=lambda mode: {
                "run_id": "distill_run",
                "status": "running",
                "pid": 123,
                "run_path": str(tmp_path / "runs" / "distill_run"),
            },
        )
        output = _run_distill_model(
            DistillModelInput(teacher_checkpoint=str(teacher), dataset_path=dataset)
        )

    assert output.run_id == "distill_run"
    assert start.call_args.args[0].extra_args["teacher_checkpoint"] == str(teacher)


def test_sync_to_mlflow_requires_optional_dependency(tmp_path: Path, monkeypatch) -> None:
    """MLflow sync should be explicitly optional."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    _seed_complete_run(tmp_path, run_id="mlflow_run")

    with patch("fovux.tools.sync_to_mlflow.importlib.import_module", side_effect=ImportError):
        with pytest.raises(FovuxError, match="MLflow integration requires"):
            _run_sync_to_mlflow("mlflow_run", "http://localhost:5000")


def test_train_adjust_writes_control_file(tmp_path: Path, monkeypatch) -> None:
    """Live training adjustment should persist the requested control payload."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    run_dir = _seed_complete_run(tmp_path, run_id="adjust_me")
    registry = RunRegistry(ensure_fovux_dirs(tmp_path).runs_db)
    registry.update_status("adjust_me", "running", pid=123)

    output = _run_train_adjust(
        TrainAdjustInput(run_id="adjust_me", learning_rate=0.001, mosaic=False)
    )

    assert output.control_path == run_dir / "control.json"
    control = json.loads(output.control_path.read_text(encoding="utf-8"))
    assert control["learning_rate"] == 0.001
    assert control["mosaic"] is False


def test_train_adjust_rejects_unknown_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    ensure_fovux_dirs(tmp_path)

    with pytest.raises(FovuxTrainingRunNotFoundError):
        _run_train_adjust(TrainAdjustInput(run_id="ghost", learning_rate=0.01))
