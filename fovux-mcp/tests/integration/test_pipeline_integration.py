"""Integration and contract tests for training worker, export, and inference pipelines."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from fovux.core.processes import ProcessIdentity
from fovux.schemas.export import ExportOnnxInput, ExportTfliteInput
from fovux.schemas.inference import InferImageInput, InferRtspInput
from fovux.schemas.training import TrainStartInput, TrainStatusInput
from fovux.tools.export_onnx import _run_export_onnx
from fovux.tools.export_tflite import _run_export_tflite
from fovux.tools.infer_image import _run_infer_image
from fovux.tools.infer_rtsp import _run_infer_rtsp
from fovux.tools.train_start import _run_train_start
from fovux.tools.train_status import _run_train_status


class DummyTensor:
    """Mock tensor wrapper that implements cpu(), numpy(), and tolist()."""

    def __init__(self, data: list[object]) -> None:
        self.data = data

    def cpu(self) -> DummyTensor:
        return self

    def numpy(self) -> DummyTensor:
        return self

    def tolist(self) -> list[object]:
        return self.data


@pytest.fixture()
def mock_dataset_and_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    """Set up temporary dataset and weights checkpoint for testing."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    # Create mock dataset
    ds = tmp_path / "dataset"
    (ds / "images" / "train").mkdir(parents=True)
    (ds / "labels" / "train").mkdir(parents=True)
    (ds / "data.yaml").write_text("nc: 1\nnames: ['object']\n", encoding="utf-8")

    # Create mock checkpoint
    ckpt = tmp_path / "best.pt"
    ckpt.write_bytes(b"mock_weights")
    return ds, ckpt


def test_export_onnx_and_tflite_contract(
    mock_dataset_and_checkpoint: tuple[Path, Path],
) -> None:
    """Validate contract and pipeline flow for ONNX and TFLite exports."""
    ds, ckpt = mock_dataset_and_checkpoint

    # Mock Ultralytics model export
    fake_model = MagicMock()
    fake_model.export.return_value = ds.parent / "best.onnx"

    # Write a dummy onnx file so size calculations work
    (ds.parent / "best.onnx").write_bytes(b"onnx_content")

    with (
        patch("fovux.tools.export_onnx.load_yolo_model", return_value=fake_model),
        patch("fovux.tools.export_onnx._check_parity", return_value=(True, 0.0)),
    ):
        out_onnx = _run_export_onnx(
            ExportOnnxInput(
                checkpoint=str(ckpt),
                output_path=ds.parent / "output.onnx",
                parity_check=True,
            )
        )
        assert out_onnx.onnx_path == ds.parent / "output.onnx"
        assert out_onnx.parity_passed is True
        assert out_onnx.model_size_bytes == len(b"onnx_content")

    # Mock TFLite model export
    fake_tflite_model = MagicMock()
    fake_tflite_model.export.return_value = ds.parent / "best_saved_model" / "best_float32.tflite"
    (ds.parent / "best_saved_model").mkdir()
    (ds.parent / "best_saved_model" / "best_float32.tflite").write_bytes(b"tflite_content")

    with patch(
        "fovux.tools.export_tflite.load_yolo_model",
        return_value=fake_tflite_model,
    ):
        out_tflite = _run_export_tflite(
            ExportTfliteInput(
                checkpoint=str(ckpt),
                output_path=ds.parent / "output.tflite",
            )
        )
        assert out_tflite.tflite_path == ds.parent / "output.tflite"
        assert out_tflite.model_size_bytes == len(b"tflite_content")


def test_inference_and_rtsp_pipeline_contract(
    mock_dataset_and_checkpoint: tuple[Path, Path],
) -> None:
    """Validate contract and pipeline flow for Image and RTSP inference."""
    ds, ckpt = mock_dataset_and_checkpoint

    # Mock image inference
    fake_result = MagicMock()
    fake_result.boxes.cls = DummyTensor([0])
    fake_result.boxes.conf = DummyTensor([0.95])
    fake_result.boxes.xyxy = DummyTensor([[10.0, 10.0, 50.0, 50.0]])
    fake_result.names = {0: "object"}
    fake_result.path = "sample.jpg"
    fake_result.orig_shape = (100, 100)
    fake_result.orig_img = np.zeros((100, 100, 3), dtype=np.uint8)

    fake_model = MagicMock()
    fake_model.predict.return_value = [fake_result]

    # Save a sample image
    sample_img = ds / "images" / "train" / "sample.jpg"
    from PIL import Image

    Image.new("RGB", (100, 100)).save(sample_img)

    with patch("fovux.tools.infer_image.load_yolo_model", return_value=fake_model):
        out_img = _run_infer_image(InferImageInput(checkpoint=str(ckpt), image_path=sample_img))
        assert len(out_img.detections) == 1
        assert out_img.detections[0].class_name == "object"
        assert out_img.detections[0].confidence == pytest.approx(0.95)

    # Mock RTSP Stream Inference
    class FakeCapture:
        def __init__(self, frames: list[tuple[bool, np.ndarray | None]]) -> None:
            self.frames = frames
            self.idx = 0
            self._released = False

        def read(self) -> tuple[bool, np.ndarray | None]:
            if self.idx >= len(self.frames):
                return False, None
            val = self.frames[self.idx]
            self.idx += 1
            return val

        def isOpened(self) -> bool:  # noqa: N802
            return not self._released and self.idx < len(self.frames)

        def release(self) -> None:
            self._released = True

    class FakeWriter:
        def __init__(self) -> None:
            self.written: list[np.ndarray] = []
            self.released = False

        def write(self, frame: np.ndarray) -> None:
            self.written.append(frame)

        def release(self) -> None:
            self.released = True

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    capture = FakeCapture([(True, frame), (True, frame), (False, None)])
    writer = FakeWriter()

    with (
        patch("fovux.tools.infer_rtsp.load_yolo_model", return_value=fake_model),
        patch(
            "fovux.tools.infer_rtsp._open_rtsp_capture",
            side_effect=[capture, FakeCapture([])],
        ),
        patch(
            "fovux.tools.infer_rtsp._infer_rtsp_frame",
            return_value=(fake_result, frame),
        ),
        patch("fovux.tools.infer_rtsp._open_video_writer", return_value=writer),
        patch(
            "fovux.tools.infer_rtsp.time.perf_counter",
            side_effect=[0.0, 0.0, 0.1, 0.2, 1.5, 2.0],
        ),
    ):
        out_rtsp = _run_infer_rtsp(
            InferRtspInput(
                checkpoint=str(ckpt),
                rtsp_url="rtsp://localhost:554/live",
                duration_seconds=1,
                save_video=True,
                output_path=ds.parent / "stream.mp4",
            )
        )
        assert out_rtsp.frames_processed >= 1
        assert out_rtsp.detection_count == out_rtsp.frames_processed
        assert writer.released is True
        assert len(writer.written) >= 1


def test_train_worker_integration_flow(
    mock_dataset_and_checkpoint: tuple[Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test full training worker launch, status updates, and progress monitoring."""
    ds, ckpt = mock_dataset_and_checkpoint

    # Mock subprocess.Popen for launching the training worker
    class FakeProcess:
        def __init__(self, run_dir: Path) -> None:
            self.pid = 98765
            self.run_dir = run_dir
            self.status_file = run_dir / "status.json"

        def poll(self) -> int | None:
            # Simulate worker run completion
            return 0

    def fake_popen(
        args: list[str],
        *args_other: object,
        **kwargs: object,
    ) -> FakeProcess:
        run_dir_str = args[-1]
        run_dir = Path(run_dir_str)
        # Simulate worker creating status file and metrics logs
        status_data = {
            "status": "complete",
            "pid": 98765,
            "epoch": 2,
        }
        (run_dir / "status.json").write_text(json.dumps(status_data), encoding="utf-8")

        metrics_data = {
            "epoch": 2,
            "metrics": {"metrics/mAP50(B)": 0.88},
        }
        (run_dir / "metrics.jsonl").write_text(
            json.dumps(metrics_data) + "\n",
            encoding="utf-8",
        )
        return FakeProcess(run_dir)

    def fake_capture(pid: int, command: list[str], cwd: Path) -> ProcessIdentity:
        return ProcessIdentity(
            pid=pid,
            command_fingerprint="test-fingerprint",
            cwd=str(cwd),
            start_marker="test-start",
            process_group_id=None,
            platform="test-platform",
        )

    monkeypatch.setattr(
        "fovux.tools.train_start.capture_process_identity",
        fake_capture,
    )

    with patch("fovux.tools.train_start.subprocess.Popen", side_effect=fake_popen):
        out_start = _run_train_start(
            TrainStartInput(
                dataset_path=ds,
                model="yolov8n.pt",
                epochs=2,
            )
        )
        assert out_start.run_id
        assert out_start.pid == 98765

        # Check status tool parses it correctly
        out_status = _run_train_status(TrainStatusInput(run_id=out_start.run_id))
        assert out_status.status == "complete"
        assert out_status.best_map50 == pytest.approx(0.88)
