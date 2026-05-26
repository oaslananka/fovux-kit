"""Public MCP tool boundary tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch


class Dumpable:
    """Tiny stand-in for Pydantic output models."""

    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def model_dump(self, *, mode: str = "python") -> dict[str, object]:
        assert mode == "json"
        return self._payload


def test_export_and_eval_wrappers_return_json_payloads(tmp_path: Path) -> None:
    """Export/eval public wrappers should validate inputs and serialize outputs."""
    checkpoint = str(tmp_path / "model.pt")
    dataset = str(tmp_path / "dataset")
    Path(dataset).mkdir()

    with patch(
        "fovux.tools.export_tflite._run_export_tflite",
        return_value=Dumpable({"output_path": "model.tflite"}),
    ):
        from fovux.tools.export_tflite import export_tflite

        assert export_tflite(checkpoint)["output_path"] == "model.tflite"

    with patch(
        "fovux.tools.export_onnx._run_export_onnx",
        return_value=Dumpable({"output_path": "model.onnx"}),
    ):
        from fovux.tools.export_onnx import export_onnx

        assert export_onnx(checkpoint, parity_check=False)["output_path"] == "model.onnx"

    with patch("fovux.tools.eval_run._run_eval", return_value=Dumpable({"map50": 0.4})):
        from fovux.tools.eval_run import eval_run

        assert eval_run(checkpoint, dataset)["map50"] == 0.4

    with patch(
        "fovux.tools.eval_compare._run_eval_compare",
        return_value=Dumpable({"winner": "a"}),
    ):
        from fovux.tools.eval_compare import eval_compare

        assert eval_compare(["run_a", "run_b"], dataset)["winner"] == "a"

    with patch(
        "fovux.tools.eval_per_class._run_eval_per_class",
        return_value=Dumpable({"classes": []}),
    ):
        from fovux.tools.eval_per_class import eval_per_class

        assert eval_per_class(checkpoint, dataset)["classes"] == []


def test_inference_and_roadmap_wrappers_return_json_payloads(tmp_path: Path) -> None:
    """Inference and experimental public wrappers should preserve typed errors at the boundary."""
    image = tmp_path / "image.jpg"
    image.write_bytes(b"fake")
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    output = tmp_path / "out"

    with patch("fovux.tools.infer_image._run_infer_image", return_value=Dumpable({"count": 1})):
        from fovux.tools.infer_image import infer_image

        assert infer_image("model.pt", str(image))["count"] == 1

    with patch(
        "fovux.tools.infer_ensemble._run_infer_ensemble",
        return_value=Dumpable({"detection_count": 1}),
    ):
        from fovux.tools.infer_ensemble import infer_ensemble

        assert infer_ensemble(["a.pt", "b.pt"], str(image))["detection_count"] == 1

    with patch(
        "fovux.tools.model_compare_visual._run_model_compare_visual",
        return_value=Dumpable({"output_path": "comparison.jpg"}),
    ):
        from fovux.tools.model_compare_visual import model_compare_visual

        assert model_compare_visual("a.pt", "b.pt", str(image))["output_path"] == "comparison.jpg"

    with patch(
        "fovux.tools.dataset_augment._run_dataset_augment",
        return_value=Dumpable({"output_path": str(output)}),
    ):
        from fovux.tools.dataset_augment import dataset_augment

        assert dataset_augment(str(dataset), ["flip_h"], 2, str(output))["output_path"] == str(
            output
        )

    with patch(
        "fovux.tools.active_learning_select._run_active_learning_select",
        return_value=Dumpable({"selected": []}),
    ):
        from fovux.tools.active_learning_select import active_learning_select

        assert active_learning_select("model.pt", str(dataset))["selected"] == []


def test_management_and_optional_integration_wrappers_return_json_payloads(tmp_path: Path) -> None:
    """Management wrappers should expose stable JSON responses."""
    with patch(
        "fovux.tools.distill_model._run_distill_model",
        return_value=Dumpable({"run_id": "distill"}),
    ):
        from fovux.tools.distill_model import distill_model

        assert distill_model("teacher.pt", str(tmp_path), "yolov8n.pt")["run_id"] == "distill"

    with patch(
        "fovux.tools.run_archive._run_run_archive",
        return_value=Dumpable({"run_id": "run1", "status": "archived"}),
    ):
        from fovux.tools.run_archive import run_archive

        assert run_archive("run1")["status"] == "archived"

    with patch(
        "fovux.tools.train_adjust._run_train_adjust",
        return_value=Dumpable({"run_id": "run1"}),
    ):
        from fovux.tools.train_adjust import train_adjust

        assert train_adjust("run1", learning_rate=0.01)["run_id"] == "run1"

    with patch(
        "fovux.tools.sync_to_mlflow._run_sync_to_mlflow",
        return_value=Dumpable({"run_id": "run1", "metrics_logged": 2}),
    ):
        from fovux.tools.sync_to_mlflow import sync_to_mlflow

        assert sync_to_mlflow("run1", "file:///tmp/mlruns")["metrics_logged"] == 2


def test_quantization_and_benchmark_wrappers_return_json_payloads(tmp_path: Path) -> None:
    """Quantization and benchmark wrappers should serialize Pydantic results."""
    with (
        patch("fovux.tools.quantize_int8.validate_calibration_dataset"),
        patch(
            "fovux.tools.quantize_int8._run_quantize_int8",
            return_value=Dumpable({"quantized_path": "model-int8.onnx"}),
        ),
    ):
        from fovux.tools.quantize_int8 import quantize_int8

        assert (
            quantize_int8("model.pt", str(tmp_path / "calibration"))["quantized_path"]
            == "model-int8.onnx"
        )

    with patch(
        "fovux.tools.benchmark_latency._run_benchmark_latency",
        return_value=Dumpable({"latency_p95_ms": 12.0}),
    ):
        from fovux.tools.benchmark_latency import benchmark_latency

        assert benchmark_latency("model.onnx")["latency_p95_ms"] == 12.0

    with patch(
        "fovux.tools.infer_rtsp._run_infer_rtsp",
        return_value=Dumpable({"frames_processed": 0}),
    ):
        from fovux.tools.infer_rtsp import infer_rtsp

        assert infer_rtsp("model.pt", "rtsp://camera")["frames_processed"] == 0
