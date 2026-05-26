"""Tests for evaluation tools: eval_run, eval_per_class, eval_compare, eval_error_analysis."""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from fovux.core.errors import FovuxCheckpointNotFoundError, FovuxDatasetNotFoundError
from fovux.schemas.eval import (
    EvalCompareInput,
    EvalErrorAnalysisInput,
    EvalErrorAnalysisOutput,
    EvalPerClassInput,
    EvalRunInput,
)
from fovux.tools.eval_compare import _run_eval_compare
from fovux.tools.eval_error_analysis import (
    _bbox_iou,
    _extract_worst_samples,
    _load_ground_truth_samples,
    _prediction_bbox,
    _resolve_sample_key,
    _run_error_analysis,
    _yolo_error_analysis,
    _yolo_to_xyxy,
    eval_error_analysis,
)
from fovux.tools.eval_per_class import _run_eval_per_class
from fovux.tools.eval_run import _parse_val_results, _resolve_checkpoint, _run_eval

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


# ── helpers ──────────────────────────────────────────────────────────────────


def _fake_val_results(map50: float = 0.7, map50_95: float = 0.5) -> SimpleNamespace:
    box = SimpleNamespace(
        map50=map50,
        map=map50_95,
        mp=0.8,
        mr=0.75,
        ap_class_index=[0, 1],
        ap50=[map50 - 0.05, map50 + 0.05],
        ap=[map50_95 - 0.05, map50_95 + 0.05],
        p=[0.80, 0.82],
        r=[0.75, 0.77],
    )
    return SimpleNamespace(box=box, names={0: "cat", 1: "dog"}, save_dir=None)


def _make_checkpoint(tmp_path: Path, name: str = "best.pt") -> Path:
    pt = tmp_path / name
    pt.write_bytes(b"fake_weights")
    return pt


# ── _resolve_checkpoint ───────────────────────────────────────────────────────


def test_resolve_checkpoint_direct_path(tmp_path):
    pt = _make_checkpoint(tmp_path)
    assert _resolve_checkpoint(str(pt)) == pt


def test_resolve_checkpoint_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    with pytest.raises(FovuxCheckpointNotFoundError):
        _resolve_checkpoint("/no/such/model.pt")


# ── _parse_val_results ────────────────────────────────────────────────────────


def test_parse_val_results_basic(tmp_path):
    results = _fake_val_results()
    inp = EvalRunInput(checkpoint="x.pt", dataset_path=tmp_path)
    pt = _make_checkpoint(tmp_path)
    out = _parse_val_results(inp, results, 1.23, pt)
    assert abs(out.map50 - 0.7) < 1e-6
    assert len(out.per_class) == 2
    assert out.per_class[0].class_name == "cat"
    assert out.eval_duration_seconds == pytest.approx(1.23)


# ── _run_eval ─────────────────────────────────────────────────────────────────


def test_run_eval_missing_dataset_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_checkpoint(tmp_path)
    with pytest.raises(FovuxDatasetNotFoundError):
        _run_eval(EvalRunInput(checkpoint=str(pt), dataset_path=Path("/no/data")))


def test_run_eval_returns_output(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_checkpoint(tmp_path)
    (FIXTURES / "mini_yolo" / "data.yaml")  # must exist

    with patch("fovux.tools.eval_run._yolo_val", return_value=_fake_val_results(0.65, 0.45)):
        out = _run_eval(
            EvalRunInput(
                checkpoint=str(pt),
                dataset_path=FIXTURES / "mini_yolo",
            )
        )
    assert abs(out.map50 - 0.65) < 1e-6
    assert out.precision == pytest.approx(0.8)
    assert len(out.per_class) == 2


# ── _run_eval_per_class ───────────────────────────────────────────────────────


def test_eval_per_class_sort_ascending(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_checkpoint(tmp_path)
    with patch("fovux.tools.eval_run._yolo_val", return_value=_fake_val_results(0.7, 0.5)):
        out = _run_eval_per_class(
            EvalPerClassInput(
                checkpoint=str(pt),
                dataset_path=FIXTURES / "mini_yolo",
                sort_by="map50",
                ascending=True,
            )
        )
    maps = [s.map50 for s in out.per_class]
    assert maps == sorted(maps)


def test_eval_per_class_worst_classes(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_checkpoint(tmp_path)
    with patch("fovux.tools.eval_run._yolo_val", return_value=_fake_val_results()):
        out = _run_eval_per_class(
            EvalPerClassInput(
                checkpoint=str(pt),
                dataset_path=FIXTURES / "mini_yolo",
            )
        )
    assert len(out.worst_classes) <= 5


# ── _run_eval_compare ─────────────────────────────────────────────────────────


def test_eval_compare_ranks_by_map50(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt1 = tmp_path / "a.pt"
    pt2 = tmp_path / "b.pt"
    pt1.write_bytes(b"w1")
    pt2.write_bytes(b"w2")

    side_effects = [
        _fake_val_results(map50=0.8),
        _fake_val_results(map50=0.6),
    ]
    with patch("fovux.tools.eval_run._yolo_val", side_effect=side_effects):
        out = _run_eval_compare(
            EvalCompareInput(
                checkpoints=[str(pt1), str(pt2)],
                dataset_path=FIXTURES / "mini_yolo",
            )
        )
    assert out.results[0].map50 > out.results[1].map50
    assert out.best_map50 == str(pt1)


def test_eval_compare_empty_checkpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    out = _run_eval_compare(
        EvalCompareInput(
            checkpoints=[],
            dataset_path=FIXTURES / "mini_yolo",
        )
    )
    assert out.results == []
    assert out.best_map50 == ""


# ── _run_error_analysis ───────────────────────────────────────────────────────


def test_error_analysis_missing_dataset_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_checkpoint(tmp_path)
    with pytest.raises(FovuxDatasetNotFoundError):
        _run_error_analysis(
            EvalErrorAnalysisInput(
                checkpoint=str(pt),
                dataset_path=Path("/no/data"),
            )
        )


def test_error_analysis_returns_output(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_checkpoint(tmp_path)

    fake_results = _fake_val_results()
    fake_results.confusion_matrix = None

    with patch("fovux.tools.eval_error_analysis._yolo_error_analysis", return_value=([], [], 2, 3)):
        out = _run_error_analysis(
            EvalErrorAnalysisInput(
                checkpoint=str(pt),
                dataset_path=FIXTURES / "mini_yolo",
            )
        )
    assert out.false_positive_count == 2
    assert out.false_negative_count == 3
    assert out.eval_duration_seconds >= 0


def test_eval_error_analysis_public_wrapper_returns_json(tmp_path, monkeypatch):
    """The public MCP wrapper should serialize the structured error-analysis output."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    expected = EvalErrorAnalysisOutput(
        checkpoint=str(tmp_path / "best.pt"),
        confusion_matrix=[],
        top_errors=[],
        false_positive_count=1,
        false_negative_count=2,
        eval_duration_seconds=0.25,
    )

    with patch("fovux.tools.eval_error_analysis._run_error_analysis", return_value=expected):
        payload = eval_error_analysis(
            checkpoint=str(tmp_path / "best.pt"),
            dataset_path=str(FIXTURES / "mini_yolo"),
            split="val",
            top_n=3,
        )

    assert payload["false_positive_count"] == 1
    assert payload["false_negative_count"] == 2
    assert payload["checkpoint"] == str(tmp_path / "best.pt")


def test_yolo_error_analysis_builds_confusion_entries(tmp_path):
    dataset_path = tmp_path / "dataset"
    images_dir = dataset_path / "images" / "val"
    labels_dir = dataset_path / "labels" / "val"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    Image.new("RGB", (100, 100), color=(20, 20, 20)).save(images_dir / "sample.jpg")
    (labels_dir / "sample.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (dataset_path / "data.yaml").write_text("names: ['cat', 'dog']\n", encoding="utf-8")

    matrix = np.array(
        [
            [0, 0, 3],
            [4, 0, 0],
            [5, 0, 0],
        ],
    )
    results = SimpleNamespace(
        names={0: "cat", 1: "dog"},
        confusion_matrix=SimpleNamespace(matrix=matrix),
        jdict=[
            {
                "image_id": "sample",
                "category_id": 1,
                "score": 0.88,
                "bbox": [10.0, 10.0, 20.0, 20.0],
            }
        ],
    )
    model = SimpleNamespace(val=lambda **_kwargs: results)

    with patch("fovux.tools.eval_error_analysis.load_yolo_model", return_value=model):
        entries, top_errors, fp_count, fn_count = _yolo_error_analysis(
            tmp_path / "best.pt",
            dataset_path,
            EvalErrorAnalysisInput(
                checkpoint=str(tmp_path / "best.pt"),
                dataset_path=dataset_path,
                top_n=2,
            ),
        )

    assert [entry.count for entry in entries] == [5, 4]
    assert entries[0].true_class == "cat"
    assert entries[0].predicted_class == "background"
    assert fp_count == 3
    assert fn_count == 5
    assert len(top_errors) == 2
    assert top_errors[0].image_path.name == "sample.jpg"
    assert top_errors[0].predicted_class == "dog"
    assert top_errors[0].true_class == "background"


def test_error_analysis_helpers_cover_edge_cases(tmp_path):
    """Error-analysis helpers should handle missing samples and malformed predictions."""
    dataset_path = tmp_path / "dataset"
    assert (
        _extract_worst_samples(
            results=SimpleNamespace(jdict=[]),
            dataset_path=dataset_path,
            split="val",
            top_n=5,
            names={},
        )
        == []
    )
    assert _load_ground_truth_samples(dataset_path, "val") == {}
    assert _prediction_bbox({"bbox": "bad"}) is None
    assert _prediction_bbox({"bbox": [1, "bad", 2, 3]}) is None
    assert _bbox_iou(None, (0.0, 0.0, 1.0, 1.0)) == 0.0
    assert _bbox_iou((0.0, 0.0, 0.0, 1.0), (0.0, 0.0, 1.0, 1.0)) == 0.0
    assert _bbox_iou((0.0, 0.0, 1.0, 1.0), (2.0, 2.0, 3.0, 3.0)) == 0.0
    assert _yolo_to_xyxy(0.5, 0.5, 0.2, 0.4, 100, 50) == (40.0, 15.0, 60.0, 35.0)


def test_extract_worst_samples_skips_good_and_malformed_predictions(tmp_path):
    """Worst-sample extraction should ignore matched predictions and score real misses."""
    dataset_path = tmp_path / "dataset"
    images_dir = dataset_path / "images" / "val"
    labels_dir = dataset_path / "labels" / "val"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    Image.new("RGB", (100, 100), color=(30, 30, 30)).save(images_dir / "sample.jpg")
    Image.new("RGB", (100, 100), color=(30, 30, 30)).save(images_dir / "missing.jpg")
    (labels_dir / "sample.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (labels_dir / "missing.txt").write_text("1 0.5 0.5 0.2 0.2\n", encoding="utf-8")

    samples = _load_ground_truth_samples(dataset_path, "val")
    assert _resolve_sample_key({"image_id": ""}, samples) is None
    assert _resolve_sample_key({"file_name": "sample.jpg"}, samples) == "sample"

    results = SimpleNamespace(
        jdict=[
            "not-a-dict",
            {"image_id": "unknown", "category_id": 0, "score": 0.5, "bbox": [1, 1, 2, 2]},
            {"image_id": "sample", "category_id": "bad", "score": 0.5, "bbox": [1, 1, 2, 2]},
            {"image_id": "sample", "category_id": 0, "score": 0.9, "bbox": [40, 40, 20, 20]},
            {"image_id": "sample", "category_id": 1, "score": 0.8, "bbox": [1, 1, 10, 10]},
        ]
    )

    errors = _extract_worst_samples(
        results=results,
        dataset_path=dataset_path,
        split="val",
        top_n=5,
        names={0: "cat", 1: "dog"},
    )

    assert errors[0].predicted_class == "dog"
    assert errors[0].true_class == "background"
    assert any(
        error.predicted_class == "background" and error.true_class == "dog" for error in errors
    )


def test_eval_defaults_use_auto_device() -> None:
    """The evaluation surface should default to automatic device selection."""
    assert EvalRunInput(checkpoint="x.pt", dataset_path=Path(".")).device == "auto"
    assert EvalErrorAnalysisInput(checkpoint="x.pt", dataset_path=Path(".")).device == "auto"
    assert inspect.signature(eval_error_analysis).parameters["device"].default == "auto"
