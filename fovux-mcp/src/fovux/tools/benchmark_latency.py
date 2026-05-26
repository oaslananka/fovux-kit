"""benchmark_latency — measure local inference latency for exported models."""

from __future__ import annotations

import importlib
import time
import tracemalloc
from pathlib import Path
from typing import Any

import numpy as np

from fovux.core.errors import FovuxCheckpointNotFoundError, FovuxInferenceError
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.schemas.inference import BenchmarkLatencyInput, BenchmarkLatencyOutput
from fovux.server import mcp


@mcp.tool()
def benchmark_latency(
    model_path: str,
    backend: str = "onnxruntime",
    device: str = "auto",
    imgsz: int = 640,
    batch_size: int = 1,
    num_warmup: int = 10,
    num_iterations: int = 100,
    threads: int = 4,
) -> dict[str, Any]:
    """Benchmark p50/p95/p99 latency and throughput for a local model artifact."""
    inp = BenchmarkLatencyInput(
        model_path=Path(model_path),
        backend=backend,  # type: ignore[arg-type]
        device=device,
        imgsz=imgsz,
        batch_size=batch_size,
        num_warmup=num_warmup,
        num_iterations=num_iterations,
        threads=threads,
    )
    with tool_event(
        "benchmark_latency",
        model_path=model_path,
        backend=backend,
        device=device,
    ):
        return _run_benchmark_latency(inp).model_dump(mode="json")


def _run_benchmark_latency(inp: BenchmarkLatencyInput) -> BenchmarkLatencyOutput:
    model_path = inp.model_path.expanduser().resolve()
    if not model_path.exists():
        raise FovuxCheckpointNotFoundError(str(model_path))

    if inp.backend == "onnxruntime":
        timings_ms, peak_memory_mb = _benchmark_onnxruntime(model_path, inp)
    elif inp.backend == "pytorch":
        timings_ms, peak_memory_mb = _benchmark_pytorch(model_path, inp)
    elif inp.backend == "tflite":
        timings_ms, peak_memory_mb = _benchmark_tflite(model_path, inp)
    elif inp.backend == "tensorrt":
        timings_ms, peak_memory_mb = _benchmark_tensorrt(model_path, inp)
    else:  # pragma: no cover - guarded by schema
        raise FovuxInferenceError(f"Unsupported backend: {inp.backend}")

    latency = np.asarray(timings_ms, dtype=float)
    mean_ms = float(latency.mean()) if latency.size else 0.0

    return BenchmarkLatencyOutput(
        backend=inp.backend,
        device=inp.device,
        num_iterations=inp.num_iterations,
        latency_p50_ms=float(np.percentile(latency, 50)) if latency.size else 0.0,
        latency_p95_ms=float(np.percentile(latency, 95)) if latency.size else 0.0,
        latency_p99_ms=float(np.percentile(latency, 99)) if latency.size else 0.0,
        latency_mean_ms=mean_ms,
        latency_std_ms=float(latency.std()) if latency.size else 0.0,
        throughput_fps=(inp.batch_size * 1000.0 / mean_ms) if mean_ms else 0.0,
        peak_memory_mb=peak_memory_mb,
    )


def _benchmark_onnxruntime(
    model_path: Path,
    inp: BenchmarkLatencyInput,
) -> tuple[list[float], float]:
    ort: Any = importlib.import_module("onnxruntime")
    so = ort.SessionOptions()
    so.intra_op_num_threads = inp.threads
    session = ort.InferenceSession(str(model_path), sess_options=so)

    dummy = np.random.rand(inp.batch_size, 3, inp.imgsz, inp.imgsz).astype(np.float32)
    input_name = session.get_inputs()[0].name

    tracemalloc.start()
    try:
        for _ in range(inp.num_warmup):
            session.run(None, {input_name: dummy})
        timings = []
        for _ in range(inp.num_iterations):
            t0 = time.perf_counter()
            session.run(None, {input_name: dummy})
            timings.append((time.perf_counter() - t0) * 1000.0)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    return timings, peak / (1024 * 1024)


def _benchmark_pytorch(
    model_path: Path,
    inp: BenchmarkLatencyInput,
) -> tuple[list[float], float]:
    model = load_yolo_model(model_path)
    dummy = np.random.randint(0, 255, (inp.imgsz, inp.imgsz, 3), dtype=np.uint8)
    sources = [dummy.copy() for _ in range(inp.batch_size)]

    tracemalloc.start()
    try:
        for _ in range(inp.num_warmup):
            model.predict(source=sources, imgsz=inp.imgsz, device=inp.device, verbose=False)
        timings = []
        for _ in range(inp.num_iterations):
            t0 = time.perf_counter()
            model.predict(source=sources, imgsz=inp.imgsz, device=inp.device, verbose=False)
            timings.append((time.perf_counter() - t0) * 1000.0)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    return timings, peak / (1024 * 1024)


def _benchmark_tflite(
    model_path: Path,
    inp: BenchmarkLatencyInput,
) -> tuple[list[float], float]:
    try:
        tflite_module: Any = importlib.import_module("tflite_runtime.interpreter")
    except ImportError:
        try:
            tflite_module = importlib.import_module("tensorflow.lite")
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise FovuxInferenceError(
                "TFLite backend is unavailable.",
                hint="Install `tflite-runtime` or TensorFlow Lite to benchmark TFLite models.",
            ) from exc

    interpreter = tflite_module.Interpreter(model_path=str(model_path), num_threads=inp.threads)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()[0]
    output_index = interpreter.get_output_details()[0]["index"]
    dummy = np.random.rand(*input_details["shape"]).astype(np.float32)

    tracemalloc.start()
    try:
        for _ in range(inp.num_warmup):
            interpreter.set_tensor(input_details["index"], dummy)
            interpreter.invoke()
            interpreter.get_tensor(output_index)
        timings = []
        for _ in range(inp.num_iterations):
            t0 = time.perf_counter()
            interpreter.set_tensor(input_details["index"], dummy)
            interpreter.invoke()
            interpreter.get_tensor(output_index)
            timings.append((time.perf_counter() - t0) * 1000.0)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    return timings, peak / (1024 * 1024)


def _benchmark_tensorrt(
    model_path: Path,
    inp: BenchmarkLatencyInput,
) -> tuple[list[float], float]:
    raise FovuxInferenceError(
        "TensorRT benchmarking is not available in this environment.",
        hint=(
            f"Provide a TensorRT-capable runtime to benchmark {model_path.name} on {inp.device}."
        ),
    )
