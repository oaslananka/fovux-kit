"""Tests for local latency benchmarking backends."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from fovux.core.errors import FovuxCheckpointNotFoundError, FovuxInferenceError
from fovux.schemas.inference import BenchmarkLatencyInput
from fovux.tools import benchmark_latency as benchmark_module
from fovux.tools.benchmark_latency import _run_benchmark_latency


def _artifact(tmp_path: Path, name: str = "model.onnx") -> Path:
    path = tmp_path / name
    path.write_bytes(b"model")
    return path


def test_benchmark_missing_model_raises(tmp_path: Path) -> None:
    """Benchmarking should reject missing local artifacts before loading runtimes."""
    with pytest.raises(FovuxCheckpointNotFoundError):
        _run_benchmark_latency(
            BenchmarkLatencyInput(model_path=tmp_path / "missing.onnx", backend="onnxruntime")
        )


def test_benchmark_onnxruntime_uses_mock_session(tmp_path: Path) -> None:
    """ONNX Runtime benchmarks should report timing percentiles from session runs."""
    model_path = _artifact(tmp_path)

    class _SessionOptions:
        intra_op_num_threads = 0

    class _Session:
        def get_inputs(self) -> list[SimpleNamespace]:
            return [SimpleNamespace(name="images")]

        def run(self, *_args: object, **_kwargs: object) -> list[np.ndarray]:
            return [np.zeros((1, 1), dtype=np.float32)]

    fake_ort = SimpleNamespace(
        SessionOptions=_SessionOptions,
        InferenceSession=lambda *_args, **_kwargs: _Session(),
    )

    with (
        patch.object(benchmark_module.importlib, "import_module", return_value=fake_ort),
        patch.object(
            benchmark_module.time,
            "perf_counter",
            side_effect=[0.0, 0.010, 0.020, 0.050],
        ),
    ):
        output = _run_benchmark_latency(
            BenchmarkLatencyInput(
                model_path=model_path,
                backend="onnxruntime",
                imgsz=8,
                num_warmup=1,
                num_iterations=2,
            )
        )

    assert output.backend == "onnxruntime"
    assert output.num_iterations == 2
    assert output.latency_p50_ms == pytest.approx(20.0)
    assert output.throughput_fps > 0


def test_benchmark_pytorch_uses_ultralytics_adapter(tmp_path: Path) -> None:
    """PyTorch benchmarks should call the YOLO adapter without importing ONNX Runtime."""
    model_path = _artifact(tmp_path, "model.pt")
    fake_model = SimpleNamespace(predict=lambda **_kwargs: [object()])

    with (
        patch.object(benchmark_module, "load_yolo_model", return_value=fake_model),
        patch.object(
            benchmark_module.time,
            "perf_counter",
            side_effect=[1.0, 1.004, 2.0, 2.006],
        ),
    ):
        output = _run_benchmark_latency(
            BenchmarkLatencyInput(
                model_path=model_path,
                backend="pytorch",
                imgsz=8,
                num_warmup=1,
                num_iterations=2,
            )
        )

    assert output.backend == "pytorch"
    assert output.latency_mean_ms == pytest.approx(5.0)


def test_benchmark_tflite_uses_mock_interpreter(tmp_path: Path) -> None:
    """TFLite benchmarks should drive the interpreter tensor lifecycle."""
    model_path = _artifact(tmp_path, "model.tflite")

    class _Interpreter:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.invocations = 0

        def allocate_tensors(self) -> None:
            return None

        def get_input_details(self) -> list[dict[str, object]]:
            return [{"index": 0, "shape": [1, 3, 8, 8]}]

        def get_output_details(self) -> list[dict[str, int]]:
            return [{"index": 0}]

        def set_tensor(self, _index: int, _value: np.ndarray) -> None:
            return None

        def invoke(self) -> None:
            self.invocations += 1

        def get_tensor(self, _index: int) -> np.ndarray:
            return np.zeros((1, 1), dtype=np.float32)

    fake_tflite = SimpleNamespace(Interpreter=_Interpreter)

    with (
        patch.object(benchmark_module.importlib, "import_module", return_value=fake_tflite),
        patch.object(
            benchmark_module.time,
            "perf_counter",
            side_effect=[3.0, 3.002, 4.0, 4.004],
        ),
    ):
        output = _run_benchmark_latency(
            BenchmarkLatencyInput(
                model_path=model_path,
                backend="tflite",
                imgsz=8,
                num_warmup=1,
                num_iterations=2,
            )
        )

    assert output.backend == "tflite"
    assert output.latency_p95_ms == pytest.approx(3.9)


def test_benchmark_tensorrt_reports_runtime_requirement(tmp_path: Path) -> None:
    """TensorRT remains explicit about requiring a local TensorRT-capable runtime."""
    model_path = _artifact(tmp_path, "model.engine")

    with pytest.raises(FovuxInferenceError, match="TensorRT benchmarking"):
        _run_benchmark_latency(BenchmarkLatencyInput(model_path=model_path, backend="tensorrt"))
