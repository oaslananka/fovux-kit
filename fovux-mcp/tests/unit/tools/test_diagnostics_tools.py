"""Tests for diagnostics, profiling, batch inference, and annotation quality tools."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

from fovux.core.doctor import _detect_gpu, collect_doctor_report
from fovux.schemas.diagnostics import AnnotationQualityCheckInput, ModelProfileInput
from fovux.schemas.inference import InferBatchInput
from fovux.tools.annotation_quality_check import (
    _run_annotation_quality_check,
    annotation_quality_check,
)
from fovux.tools.fovux_doctor import fovux_doctor
from fovux.tools.infer_batch import _run_infer_batch, infer_batch
from fovux.tools.model_profile import _extract_gflops, _run_model_profile, model_profile


class _FakeParameter:
    def __init__(self, size: int, requires_grad: bool = True) -> None:
        self._size = size
        self.requires_grad = requires_grad

    def numel(self) -> int:
        return self._size


class _FakeRawModel:
    def parameters(self) -> list[_FakeParameter]:
        return [_FakeParameter(2_000_000), _FakeParameter(500_000, requires_grad=False)]

    def modules(self) -> list[int]:
        return [1, 2, 3, 4]


def _fake_batch_result() -> SimpleNamespace:
    boxes = SimpleNamespace(
        cls=[0.0],
        conf=[0.91],
        xyxy=[[4.0, 6.0, 20.0, 24.0]],
    )
    return SimpleNamespace(
        boxes=boxes,
        names={0: "cat"},
        plot=lambda: np.zeros((32, 32, 3), dtype=np.uint8),
    )


def test_collect_doctor_report_and_tool_align(tmp_fovux_home: Path) -> None:
    """The MCP doctor tool should be a thin wrapper over the shared report helper."""
    with patch("fovux.core.doctor.httpx.get", side_effect=RuntimeError("offline")):
        report = collect_doctor_report()
        tool_payload = fovux_doctor()

    assert tool_payload["python"] == report.python
    assert Path(tool_payload["fovux_home"]["path"]) == tmp_fovux_home


def test_doctor_report_includes_release_gate_health(tmp_fovux_home: Path) -> None:
    """Doctor output should include disk, runtime, license, and resource snapshots."""
    with patch("fovux.core.doctor.httpx.get", side_effect=RuntimeError("offline")):
        report = collect_doctor_report()

    assert report.fovux_home.disk_low is False
    assert report.system.active_runs == 0
    assert report.system.ram_total_gb >= 0
    assert any("Ultralytics" in notice for notice in report.license_notices)
    assert "python_supported" in report.requirements


def test_doctor_gpu_health_includes_cuda_memory() -> None:
    """CUDA diagnostics should include available and total memory when torch exposes it."""
    fake_cuda = SimpleNamespace(
        is_available=lambda: True,
        get_device_name=lambda _index: "RTX Test",
        mem_get_info=lambda: (8 * 1024**3, 24 * 1024**3),
    )
    fake_torch = SimpleNamespace(
        cuda=fake_cuda,
        version=SimpleNamespace(cuda="12.4"),
        backends=SimpleNamespace(cudnn=SimpleNamespace(version=lambda: 9000)),
    )

    with patch("fovux.core.doctor.importlib.import_module", return_value=fake_torch):
        gpu = _detect_gpu()

    assert gpu.available is True
    assert gpu.accelerator == "cuda"
    assert gpu.device == "RTX Test"
    assert gpu.memory_free_gb == 8.0
    assert gpu.memory_total_gb == 24.0


def test_doctor_gpu_health_handles_missing_torch() -> None:
    """GPU detection should degrade cleanly when torch is not installed."""
    with patch("fovux.core.doctor.importlib.import_module", side_effect=ImportError("missing")):
        gpu = _detect_gpu()

    assert gpu.available is False
    assert gpu.accelerator == "cpu"
    assert "torch is not installed" in gpu.detail


def test_model_profile_returns_manual_counts(tmp_path: Path) -> None:
    """Model profiling should report parameter and layer counts from the raw model."""
    checkpoint = tmp_path / "profile.pt"
    checkpoint.write_bytes(b"weights")
    fake_model = SimpleNamespace(model=_FakeRawModel(), info=lambda **_kwargs: {"gflops": 8.5})

    with patch("fovux.tools.model_profile.load_yolo_model", return_value=fake_model):
        output = _run_model_profile(ModelProfileInput(checkpoint=str(checkpoint)))

    assert output.parameters_millions == 2.5
    assert output.gradients_millions == 2.0
    assert output.layers == 4
    assert output.gflops == 8.5


def test_model_profile_public_wrapper_and_gflops_fallbacks(tmp_path: Path) -> None:
    """Public model_profile should delegate to the profiled model and parse info variants."""
    checkpoint = tmp_path / "profile.pt"
    checkpoint.write_bytes(b"weights")
    fake_model = SimpleNamespace(model=_FakeRawModel(), info=lambda **_kwargs: (0, 0, 0, 7.25))

    with patch("fovux.tools.model_profile.load_yolo_model", return_value=fake_model):
        payload = model_profile(str(checkpoint))

    assert payload["gflops"] == 7.25
    string_info = SimpleNamespace(info=lambda **_kwargs: "Model summary: 4.2 GFLOPs")
    error_info = SimpleNamespace(info=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError()))
    assert _extract_gflops(string_info, 640) == 4.2
    assert _extract_gflops(SimpleNamespace(info=lambda **_kwargs: object()), 640) == 0.0
    assert _extract_gflops(error_info, 640) == 0.0


def test_infer_batch_writes_json_manifest(tmp_path: Path) -> None:
    """Batch inference should create a manifest for all discovered images."""
    checkpoint = tmp_path / "batch.pt"
    checkpoint.write_bytes(b"weights")
    input_dir = tmp_path / "images"
    input_dir.mkdir()
    for name in ("a.jpg", "b.jpg"):
        Image.new("RGB", (32, 32), color=(120, 20, 20)).save(input_dir / name)

    fake_model = SimpleNamespace(
        predict=lambda **_kwargs: [_fake_batch_result(), _fake_batch_result()]
    )
    with patch("fovux.tools.infer_batch.load_yolo_model", return_value=fake_model):
        output = _run_infer_batch(
            InferBatchInput(
                checkpoint=str(checkpoint),
                input_dir=input_dir,
                output_dir=tmp_path / "batch-output",
                save_annotated=False,
                export_format="json",
            )
        )

    assert output.processed_images == 2
    assert output.detection_count == 2
    payload = json.loads(output.manifest_path.read_text(encoding="utf-8"))
    assert len(payload) == 2


def test_infer_batch_public_wrapper_writes_csv_and_annotations(tmp_path: Path) -> None:
    """The public batch tool should persist CSV output and optional rendered previews."""
    checkpoint = tmp_path / "batch.pt"
    checkpoint.write_bytes(b"weights")
    input_dir = tmp_path / "images"
    input_dir.mkdir()
    Image.new("RGB", (32, 32), color=(120, 20, 20)).save(input_dir / "a.jpg")

    fake_model = SimpleNamespace(predict=lambda **_kwargs: [_fake_batch_result()])
    with patch("fovux.tools.infer_batch.load_yolo_model", return_value=fake_model):
        payload = infer_batch(
            checkpoint=str(checkpoint),
            input_dir=str(input_dir),
            output_dir=str(tmp_path / "csv-output"),
            export_format="csv",
            save_annotated=True,
        )

    manifest_path = Path(payload["manifest_path"])
    assert manifest_path.name == "predictions.csv"
    assert manifest_path.exists()
    assert Path(payload["annotated_dir"], "a.jpg").exists()


def test_infer_batch_writes_yolo_label_exports(tmp_path: Path) -> None:
    """YOLO-label export should write one label file per processed image."""
    checkpoint = tmp_path / "batch.pt"
    checkpoint.write_bytes(b"weights")
    input_dir = tmp_path / "images"
    input_dir.mkdir()
    Image.new("RGB", (32, 32), color=(120, 20, 20)).save(input_dir / "a.jpg")

    fake_model = SimpleNamespace(predict=lambda **_kwargs: [_fake_batch_result()])
    with patch("fovux.tools.infer_batch.load_yolo_model", return_value=fake_model):
        output = _run_infer_batch(
            InferBatchInput(
                checkpoint=str(checkpoint),
                input_dir=input_dir,
                output_dir=tmp_path / "labels-output",
                export_format="yolo_labels",
                save_annotated=False,
            )
        )

    label_file = output.manifest_path / "a.txt"
    assert label_file.exists()
    assert label_file.read_text(encoding="utf-8").startswith("0 ")


def test_annotation_quality_check_reports_common_issues(tmp_path: Path) -> None:
    """Annotation quality checks should flag invalid class ids and tiny boxes."""
    dataset_path = tmp_path / "dataset"
    images_dir = dataset_path / "images" / "train"
    labels_dir = dataset_path / "labels" / "train"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    Image.new("RGB", (64, 64), color=(20, 20, 20)).save(images_dir / "sample.jpg")
    (labels_dir / "sample.txt").write_text("3 0.5 0.5 0.001 0.001\n", encoding="utf-8")
    (dataset_path / "data.yaml").write_text("names: ['cat', 'dog']\n", encoding="utf-8")

    output = _run_annotation_quality_check(AnnotationQualityCheckInput(dataset_path=dataset_path))

    assert output.total_issue_count >= 2
    assert output.issue_counts["invalid_class_id"] >= 1
    assert output.issue_counts["tiny_bbox"] >= 1


def test_annotation_quality_check_reports_empty_oob_and_overlap(tmp_path: Path) -> None:
    """Annotation quality should cover empty, out-of-bounds, and overlapping boxes."""
    dataset_path = tmp_path / "dataset"
    images_dir = dataset_path / "images" / "train"
    labels_dir = dataset_path / "labels" / "train"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)
    Image.new("RGB", (64, 64), color=(20, 20, 20)).save(images_dir / "empty.jpg")
    Image.new("RGB", (64, 64), color=(20, 20, 20)).save(images_dir / "bad.jpg")
    (labels_dir / "empty.txt").write_text("", encoding="utf-8")
    (labels_dir / "bad.txt").write_text(
        "0 1.2 0.5 0.4 0.4\n0 0.5 0.5 0.4 0.4\n0 0.5 0.5 0.4 0.4\n",
        encoding="utf-8",
    )
    (dataset_path / "data.yaml").write_text("names: ['cat']\n", encoding="utf-8")

    payload = annotation_quality_check(str(dataset_path))

    assert payload["issue_counts"]["empty_label_file"] == 1
    assert payload["issue_counts"]["bbox_out_of_bounds"] == 1
    assert payload["issue_counts"]["overlapping_bbox"] >= 1
