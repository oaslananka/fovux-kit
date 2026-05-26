"""Tests for inference, benchmarking, and management tools."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from fovux.core.errors import (
    FovuxCheckpointNotFoundError,
    FovuxInferenceError,
    FovuxRtspConnectionError,
    FovuxTrainingRunNotFoundError,
)
from fovux.core.paths import ensure_fovux_dirs
from fovux.core.runs import RunRegistry
from fovux.schemas.inference import BenchmarkLatencyInput, InferImageInput, InferRtspInput
from fovux.schemas.management import RunCompareInput
from fovux.tools import benchmark_latency as benchmark_module
from fovux.tools.benchmark_latency import (
    _benchmark_onnxruntime,
    _benchmark_pytorch,
    _benchmark_tflite,
    _run_benchmark_latency,
)
from fovux.tools.infer_image import _run_infer_image
from fovux.tools.infer_rtsp import (
    _capture_frames,
    _CaptureState,
    _run_infer_rtsp,
)
from fovux.tools.model_list import _run_model_list
from fovux.tools.run_compare import _run_run_compare


def _make_checkpoint(tmp_path: Path, name: str = "best.pt") -> Path:
    checkpoint = tmp_path / name
    checkpoint.write_bytes(b"weights")
    return checkpoint


def _make_image(tmp_path: Path, name: str = "frame.jpg") -> Path:
    image_path = tmp_path / name
    Image.new("RGB", (32, 32), color=(200, 30, 30)).save(image_path)
    return image_path


def _fake_result() -> SimpleNamespace:
    boxes = SimpleNamespace(
        cls=np.array([0.0, 1.0]),
        conf=np.array([0.91, 0.67]),
        xyxy=np.array([[1.0, 2.0, 20.0, 24.0], [5.0, 6.0, 18.0, 19.0]]),
    )
    return SimpleNamespace(
        boxes=boxes,
        names={0: "cat", 1: "dog"},
        plot=lambda: np.zeros((32, 32, 3)),
    )


def test_infer_image_returns_detections(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    checkpoint = _make_checkpoint(tmp_path)
    image_path = _make_image(tmp_path)

    with patch("fovux.tools.infer_image._predict_image", return_value=_fake_result()):
        output = _run_infer_image(
            InferImageInput(checkpoint=str(checkpoint), image_path=image_path)
        )

    assert output.detection_count == 2
    assert output.detections_by_class == {"cat": 1, "dog": 1}


def test_infer_image_saves_visualization(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    checkpoint = _make_checkpoint(tmp_path)
    image_path = _make_image(tmp_path)
    rendered = tmp_path / "rendered.jpg"

    with (
        patch("fovux.tools.infer_image._predict_image", return_value=_fake_result()),
        patch("fovux.tools.infer_image._save_visualization", return_value=rendered),
    ):
        output = _run_infer_image(
            InferImageInput(
                checkpoint=str(checkpoint),
                image_path=image_path,
                save_image=True,
            )
        )

    assert output.output_path == rendered


def test_infer_image_missing_image_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    checkpoint = _make_checkpoint(tmp_path)

    with pytest.raises(FovuxInferenceError):
        _run_infer_image(
            InferImageInput(checkpoint=str(checkpoint), image_path=tmp_path / "missing.jpg")
        )


def test_benchmark_latency_computes_percentiles(tmp_path):
    model_path = _make_checkpoint(tmp_path, "model.onnx")

    with patch(
        "fovux.tools.benchmark_latency._benchmark_onnxruntime",
        return_value=([1.0, 2.0, 3.0, 4.0], 12.5),
    ):
        output = _run_benchmark_latency(
            BenchmarkLatencyInput(model_path=model_path, num_iterations=4)
        )

    assert output.latency_p50_ms == pytest.approx(2.5)
    assert output.peak_memory_mb == pytest.approx(12.5)
    assert output.throughput_fps > 0


def test_benchmark_latency_missing_model_raises(tmp_path):
    with pytest.raises(FovuxCheckpointNotFoundError):
        _run_benchmark_latency(BenchmarkLatencyInput(model_path=tmp_path / "missing.onnx"))


def test_benchmark_latency_tensorrt_raises_cleanly(tmp_path):
    model_path = _make_checkpoint(tmp_path, "engine.plan")
    with pytest.raises(FovuxInferenceError):
        _run_benchmark_latency(BenchmarkLatencyInput(model_path=model_path, backend="tensorrt"))


def test_benchmark_onnxruntime_helper_records_timings(tmp_path):
    """The ONNX Runtime helper should benchmark the configured number of iterations."""
    model_path = _make_checkpoint(tmp_path, "model.onnx")
    session = SimpleNamespace(
        get_inputs=lambda: [SimpleNamespace(name="images")],
        run=lambda *_args, **_kwargs: [np.zeros((1, 6), dtype=np.float32)],
    )
    fake_ort = SimpleNamespace(
        SessionOptions=lambda: SimpleNamespace(intra_op_num_threads=0),
        InferenceSession=lambda *_args, **_kwargs: session,
    )

    with (
        patch.object(benchmark_module.importlib, "import_module", return_value=fake_ort),
        patch.object(benchmark_module.tracemalloc, "start"),
        patch.object(benchmark_module.tracemalloc, "stop"),
        patch.object(
            benchmark_module.tracemalloc,
            "get_traced_memory",
            return_value=(0, 2 * 1024 * 1024),
        ),
        patch.object(benchmark_module.time, "perf_counter", side_effect=[0.0, 0.001, 1.0, 1.004]),
    ):
        timings, peak = _benchmark_onnxruntime(
            model_path,
            BenchmarkLatencyInput(model_path=model_path, num_warmup=1, num_iterations=2, threads=3),
        )

    assert timings == pytest.approx([1.0, 4.0])
    assert peak == pytest.approx(2.0)


def test_benchmark_pytorch_helper_records_timings(tmp_path):
    """The PyTorch helper should call model.predict for warmup and timed iterations."""
    model_path = _make_checkpoint(tmp_path, "model.pt")
    fake_model = SimpleNamespace(predict=lambda **_kwargs: [SimpleNamespace()])

    with (
        patch.object(benchmark_module, "load_yolo_model", return_value=fake_model),
        patch.object(benchmark_module.tracemalloc, "start"),
        patch.object(benchmark_module.tracemalloc, "stop"),
        patch.object(
            benchmark_module.tracemalloc,
            "get_traced_memory",
            return_value=(0, 3 * 1024 * 1024),
        ),
        patch.object(benchmark_module.time, "perf_counter", side_effect=[0.0, 0.002, 1.0, 1.005]),
    ):
        timings, peak = _benchmark_pytorch(
            model_path,
            BenchmarkLatencyInput(
                model_path=model_path,
                backend="pytorch",
                num_warmup=1,
                num_iterations=2,
                batch_size=2,
            ),
        )

    assert timings == pytest.approx([2.0, 5.0])
    assert peak == pytest.approx(3.0)


def test_benchmark_tflite_helper_records_timings(tmp_path):
    """The TFLite helper should benchmark a fake interpreter implementation."""
    model_path = _make_checkpoint(tmp_path, "model.tflite")

    class _FakeInterpreter:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

        def allocate_tensors(self) -> None:
            return None

        def get_input_details(self) -> list[dict[str, object]]:
            return [{"shape": (1, 3, 8, 8), "index": 0}]

        def get_output_details(self) -> list[dict[str, object]]:
            return [{"index": 1}]

        def set_tensor(self, index: int, tensor: np.ndarray) -> None:
            assert index == 0
            assert tensor.shape == (1, 3, 8, 8)

        def invoke(self) -> None:
            return None

        def get_tensor(self, index: int) -> np.ndarray:
            assert index == 1
            return np.zeros((1, 6), dtype=np.float32)

    fake_tflite = SimpleNamespace(Interpreter=_FakeInterpreter)

    with (
        patch.object(benchmark_module.importlib, "import_module", return_value=fake_tflite),
        patch.object(benchmark_module.tracemalloc, "start"),
        patch.object(benchmark_module.tracemalloc, "stop"),
        patch.object(
            benchmark_module.tracemalloc,
            "get_traced_memory",
            return_value=(0, 1024 * 1024),
        ),
        patch.object(benchmark_module.time, "perf_counter", side_effect=[0.0, 0.003, 1.0, 1.006]),
    ):
        timings, peak = _benchmark_tflite(
            model_path,
            BenchmarkLatencyInput(
                model_path=model_path,
                backend="tflite",
                num_warmup=1,
                num_iterations=2,
            ),
        )

    assert timings == pytest.approx([3.0, 6.0])
    assert peak == pytest.approx(1.0)


def test_benchmark_tflite_missing_runtime_raises_hint(tmp_path):
    """Missing TFLite runtimes should surface a helpful inference error."""
    model_path = _make_checkpoint(tmp_path, "model.tflite")

    with patch.object(
        benchmark_module.importlib,
        "import_module",
        side_effect=[ImportError("missing tflite"), ImportError("missing tensorflow")],
    ):
        with pytest.raises(FovuxInferenceError) as exc_info:
            _benchmark_tflite(
                model_path,
                BenchmarkLatencyInput(model_path=model_path, backend="tflite"),
            )

    assert "TFLite backend is unavailable" in exc_info.value.message


class _FakeCapture:
    def __init__(self, responses: list[tuple[bool, object]]) -> None:
        self._responses = responses
        self._index = 0
        self._released = False

    def isOpened(self) -> bool:  # noqa: N802 - mirrors OpenCV's VideoCapture API
        return not self._released

    def read(self) -> tuple[bool, object]:
        if self._index >= len(self._responses):
            return False, None
        response = self._responses[self._index]
        self._index += 1
        return response

    def release(self) -> None:
        self._released = True


class _FakeWriter:
    def __init__(self) -> None:
        self.frames: list[object] = []

    def write(self, frame: object) -> None:
        self.frames.append(frame)

    def release(self) -> None:
        return None


def test_infer_rtsp_processes_frames(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    checkpoint = _make_checkpoint(tmp_path)
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    capture = _FakeCapture([(True, frame), (True, frame), (False, None)])

    with (
        patch("fovux.tools.infer_rtsp.load_yolo_model", return_value=object()),
        patch("fovux.tools.infer_rtsp._open_rtsp_capture", side_effect=[capture, _FakeCapture([])]),
        patch(
            "fovux.tools.infer_rtsp._infer_rtsp_frame",
            return_value=(_fake_result(), frame),
        ),
        patch(
            "fovux.tools.infer_rtsp.time.perf_counter",
            side_effect=[0.0, 0.0, 0.2, 0.4, 1.1, 1.2],
        ),
    ):
        output = _run_infer_rtsp(
            InferRtspInput(
                checkpoint=str(checkpoint), rtsp_url="rtsp://example", duration_seconds=1
            )
        )

    assert output.frames_processed >= 1
    assert output.detection_count == output.frames_processed * 2


def test_infer_rtsp_missing_stream_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    checkpoint = _make_checkpoint(tmp_path)
    with patch(
        "fovux.tools.infer_rtsp._open_rtsp_capture",
        side_effect=FovuxRtspConnectionError("x"),
    ):
        with pytest.raises(FovuxRtspConnectionError):
            _run_infer_rtsp(
                InferRtspInput(
                    checkpoint=str(checkpoint), rtsp_url="rtsp://bad", duration_seconds=1
                )
            )


def test_infer_rtsp_saves_video(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    checkpoint = _make_checkpoint(tmp_path)
    frame = np.zeros((16, 16, 3), dtype=np.uint8)
    capture = _FakeCapture([(True, frame), (False, None)])
    writer = _FakeWriter()

    with (
        patch("fovux.tools.infer_rtsp.load_yolo_model", return_value=object()),
        patch("fovux.tools.infer_rtsp._open_rtsp_capture", side_effect=[capture, _FakeCapture([])]),
        patch(
            "fovux.tools.infer_rtsp._infer_rtsp_frame",
            return_value=(_fake_result(), frame),
        ),
        patch("fovux.tools.infer_rtsp._open_video_writer", return_value=writer),
        patch(
            "fovux.tools.infer_rtsp.time.perf_counter",
            side_effect=[0.0, 0.0, 0.2, 1.1, 1.2],
        ),
    ):
        output = _run_infer_rtsp(
            InferRtspInput(
                checkpoint=str(checkpoint),
                rtsp_url="rtsp://example",
                duration_seconds=1,
                save_video=True,
                output_path=tmp_path / "rtsp.mp4",
            )
        )

    assert output.output_path is not None
    assert len(writer.frames) == 1


def test_model_list_collects_models_and_run_weights(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    paths = ensure_fovux_dirs(tmp_path)
    registry = RunRegistry(paths.runs_db)

    (paths.models / "global.onnx").write_bytes(b"onnx")
    run_dir = paths.runs / "run_demo"
    weights_dir = run_dir / "weights"
    weights_dir.mkdir(parents=True)
    (weights_dir / "best.pt").write_bytes(b"pt")
    registry.create_run(
        run_id="run_demo",
        run_path=run_dir,
        model="yolov8n.pt",
        dataset_path=tmp_path,
        task="detect",
        epochs=3,
    )

    output = _run_model_list()
    assert output.total == 2
    assert {model.source for model in output.models} == {"models", "runs"}


def test_model_list_empty_home_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    ensure_fovux_dirs(tmp_path)
    output = _run_model_list()
    assert output.total == 0


def test_benchmark_and_inference_defaults_use_auto_device() -> None:
    """Inference-facing schemas should default to automatic device selection."""
    assert InferImageInput(checkpoint="x.pt", image_path=Path("image.jpg")).device == "auto"
    assert InferRtspInput(checkpoint="x.pt", rtsp_url="rtsp://example").device == "auto"
    assert InferRtspInput(checkpoint="x.pt", rtsp_url="rtsp://example").max_reconnect_attempts == 10
    assert BenchmarkLatencyInput(model_path=Path("model.onnx")).device == "auto"


def test_infer_rtsp_requires_output_path_when_saving_video() -> None:
    """RTSP recording should require an explicit, validated output path."""
    with pytest.raises(ValueError, match="output_path is required"):
        InferRtspInput(
            checkpoint="x.pt",
            rtsp_url="rtsp://example",
            save_video=True,
            output_path=None,
        )


class _AlwaysClosedCapture:
    def read(self) -> tuple[bool, object]:
        return False, None

    def release(self) -> None:
        return None

    def isOpened(self) -> bool:  # noqa: N802
        return False


def test_capture_frames_stops_after_max_reconnect_attempts(monkeypatch) -> None:
    """The RTSP capture loop should stop after the configured reconnect ceiling."""
    import queue
    import threading

    frame_queue: queue.Queue[object] = queue.Queue(maxsize=1)
    stop_event = threading.Event()
    state = _CaptureState()

    with (
        patch("fovux.tools.infer_rtsp._open_rtsp_capture", return_value=_AlwaysClosedCapture()),
        patch("fovux.tools.infer_rtsp.time.sleep"),
    ):
        _capture_frames(
            "rtsp://example",
            _FakeCapture([(False, None)]),
            frame_queue,
            stop_event,
            state,
            3,
        )

    assert state.connection_status == "disconnected"
    assert state.reconnect_attempts == 3


def test_run_compare_writes_report_and_chart(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    paths = ensure_fovux_dirs(tmp_path)
    registry = RunRegistry(paths.runs_db)

    for run_id, score in [("run_a", 0.61), ("run_b", 0.74)]:
        run_dir = paths.runs / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "results.csv").write_text(
            f"epoch,metrics/mAP50(B)\n0,{score - 0.1}\n1,{score}\n",
            encoding="utf-8",
        )
        registry.create_run(
            run_id=run_id,
            run_path=run_dir,
            model="yolov8n.pt",
            dataset_path=tmp_path,
            task="detect",
            epochs=2,
        )

    output = _run_run_compare(RunCompareInput())
    assert output.best_run_id == "run_b"
    assert output.report_path.exists()
    assert output.chart_path.exists()


def test_run_compare_selected_run_ids(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    paths = ensure_fovux_dirs(tmp_path)
    registry = RunRegistry(paths.runs_db)

    run_dir = paths.runs / "run_only"
    run_dir.mkdir(parents=True)
    (run_dir / "results.csv").write_text("epoch,metrics/mAP50(B)\n0,0.55\n", encoding="utf-8")
    registry.create_run(
        run_id="run_only",
        run_path=run_dir,
        model="yolov8n.pt",
        dataset_path=tmp_path,
        task="detect",
        epochs=1,
    )

    output = _run_run_compare(RunCompareInput(run_ids=["run_only"]))
    assert [run.run_id for run in output.compared_runs] == ["run_only"]


def test_run_compare_unknown_run_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    ensure_fovux_dirs(tmp_path)
    with pytest.raises(FovuxTrainingRunNotFoundError):
        _run_run_compare(RunCompareInput(run_ids=["ghost"]))
