"""Tests for export and quantization tools."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from fovux.core.errors import (
    FovuxCheckpointNotFoundError,
    FovuxDatasetEmptyError,
    FovuxDatasetNotFoundError,
    FovuxExportParityError,
)
from fovux.schemas.export import (
    ExportOnnxInput,
    ExportOnnxOutput,
    ExportTfliteInput,
    QuantizeInt8Input,
    QuantizeReportInput,
)
from fovux.tools import export_onnx as export_onnx_module
from fovux.tools.export_onnx import (
    _check_parity,
    _flatten_outputs,
    _run_export_onnx,
    _yolo_export_onnx,
    export_onnx,
)
from fovux.tools.export_tflite import _run_export_tflite
from fovux.tools.quantize_int8 import _run_quantize_int8
from fovux.tools.quantize_report import _run_quantize_report

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def _make_pt(tmp_path: Path, name: str = "best.pt", size: int = 1024) -> Path:
    pt = tmp_path / name
    pt.write_bytes(b"x" * size)
    return pt


def _make_onnx(tmp_path: Path, name: str = "best.onnx", size: int = 512) -> Path:
    onnx = tmp_path / name
    onnx.write_bytes(b"o" * size)
    return onnx


# ── export_onnx ───────────────────────────────────────────────────────────────


def test_export_onnx_missing_checkpoint_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    with pytest.raises(FovuxCheckpointNotFoundError):
        _run_export_onnx(ExportOnnxInput(checkpoint="/no/model.pt", parity_check=False))


def test_export_onnx_returns_output(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path)
    onnx = _make_onnx(tmp_path)

    with patch("fovux.tools.export_onnx._yolo_export_onnx", return_value=onnx):
        out = _run_export_onnx(ExportOnnxInput(checkpoint=str(pt), parity_check=False))

    assert out.onnx_path == onnx
    assert out.model_size_bytes == 512
    assert out.parity_passed is None


def test_export_onnx_public_wrapper_returns_json(tmp_path, monkeypatch):
    """The public MCP wrapper should serialize export_onnx output."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    onnx = _make_onnx(tmp_path)
    expected = ExportOnnxOutput(
        checkpoint=str(tmp_path / "best.pt"),
        onnx_path=onnx,
        output_path=onnx,
        export_duration_seconds=0.1,
        parity_passed=True,
        parity_max_diff=0.0,
        file_size_mb=0.001,
        opset=17,
        model_size_bytes=onnx.stat().st_size,
    )

    with patch("fovux.tools.export_onnx._run_export_onnx", return_value=expected):
        payload = export_onnx(
            checkpoint=str(tmp_path / "best.pt"),
            output_path=str(onnx),
            imgsz=320,
            opset=17,
            dynamic=False,
            simplify=False,
            half=False,
            device="cpu",
            parity_check=True,
        )

    assert payload["onnx_path"] == str(onnx)
    assert payload["parity_passed"] is True
    assert payload["opset"] == 17


def test_export_onnx_parity_check_passes(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path)
    onnx = _make_onnx(tmp_path)

    with (
        patch("fovux.tools.export_onnx._yolo_export_onnx", return_value=onnx),
        patch("fovux.tools.export_onnx._check_parity", return_value=(True, 1e-5)),
    ):
        out = _run_export_onnx(ExportOnnxInput(checkpoint=str(pt), parity_check=True))

    assert out.parity_passed is True


def test_export_onnx_parity_failure_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path)
    onnx = _make_onnx(tmp_path)

    with (
        patch("fovux.tools.export_onnx._yolo_export_onnx", return_value=onnx),
        patch("fovux.tools.export_onnx._check_parity", return_value=(False, 0.5)),
    ):
        with pytest.raises(FovuxExportParityError):
            _run_export_onnx(ExportOnnxInput(checkpoint=str(pt), parity_check=True))


def test_yolo_export_onnx_moves_result_to_requested_output(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path)
    exported = _make_onnx(tmp_path, "raw.onnx")
    target = tmp_path / "exports" / "model.onnx"
    fake_model = SimpleNamespace(export=lambda **_kwargs: exported)

    with patch("fovux.tools.export_onnx.load_yolo_model", return_value=fake_model):
        output = _yolo_export_onnx(
            pt,
            ExportOnnxInput(checkpoint=str(pt), output_path=target, parity_check=False),
        )

    assert output == target
    assert target.exists()
    assert not exported.exists()


def test_check_parity_compares_outputs(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path)
    onnx = _make_onnx(tmp_path)

    class _RawModel:
        def eval(self) -> None:
            return None

        def __call__(self, tensor: object) -> np.ndarray:
            return np.ones((1, 3, 640, 640), dtype=np.float32)

    raw_model = _RawModel()
    pt_model = SimpleNamespace(model=raw_model)

    class _NoGrad:
        def __enter__(self) -> None:
            return None

        def __exit__(self, *_args: object) -> None:
            return None

    fake_torch = SimpleNamespace(
        from_numpy=lambda array: array,
        no_grad=lambda: _NoGrad(),
    )
    session = SimpleNamespace(
        get_inputs=lambda: [SimpleNamespace(name="images")],
        run=lambda *_args, **_kwargs: [np.ones((1, 3, 640, 640), dtype=np.float32)],
    )
    fake_ort = SimpleNamespace(InferenceSession=lambda *_args, **_kwargs: session)

    with (
        patch("importlib.import_module", return_value=fake_ort),
        patch.object(export_onnx_module, "load_yolo_model", return_value=pt_model),
        patch.object(export_onnx_module, "_load_torch", return_value=fake_torch),
    ):
        passed, max_diff = _check_parity(
            pt,
            onnx,
            ExportOnnxInput(checkpoint=str(pt), parity_tolerance=1e-4),
        )

    assert passed is True
    assert max_diff == pytest.approx(0.0)


def test_check_parity_runtime_error_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path)
    onnx = _make_onnx(tmp_path)

    with patch("importlib.import_module", side_effect=RuntimeError("boom")):
        with pytest.raises(FovuxExportParityError, match="could not be executed"):
            _check_parity(
                pt,
                onnx,
                ExportOnnxInput(checkpoint=str(pt), parity_tolerance=1e-4),
            )


def test_check_parity_wraps_invalid_graph_errors(tmp_path, monkeypatch):
    """ONNX Runtime graph errors should be reported as parity errors."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path)
    onnx = _make_onnx(tmp_path)

    class _InvalidGraphError(Exception):
        pass

    def _raise_invalid_graph(_path: str) -> object:
        raise _InvalidGraphError("bad graph")

    fake_ort = SimpleNamespace(
        InvalidGraph=_InvalidGraphError,
        NoSuchFile=FileNotFoundError,
        InferenceSession=_raise_invalid_graph,
    )

    with (
        patch("fovux.tools.export_onnx._forward_pytorch", return_value=[np.zeros((1, 1))]),
        patch("importlib.import_module", return_value=fake_ort),
    ):
        with pytest.raises(FovuxExportParityError, match="could not be executed"):
            _check_parity(pt, onnx, ExportOnnxInput(checkpoint=str(pt)))


def test_check_parity_rejects_output_count_mismatch(tmp_path, monkeypatch):
    """Parity check should fail when ONNX emits a different number of outputs."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path)
    onnx = _make_onnx(tmp_path)
    session = SimpleNamespace(
        get_inputs=lambda: [SimpleNamespace(name="images")],
        run=lambda *_args, **_kwargs: [np.zeros((1, 1)), np.zeros((1, 1))],
    )
    fake_ort = SimpleNamespace(InferenceSession=lambda *_args, **_kwargs: session)

    with (
        patch("fovux.tools.export_onnx._forward_pytorch", return_value=[np.zeros((1, 1))]),
        patch("importlib.import_module", return_value=fake_ort),
    ):
        with pytest.raises(FovuxExportParityError, match="output count differs"):
            _check_parity(pt, onnx, ExportOnnxInput(checkpoint=str(pt)))


def test_check_parity_rejects_shape_mismatch_and_reports_diff(tmp_path, monkeypatch):
    """Parity check should fail on shape mismatch and return false for numeric drift."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path)
    onnx = _make_onnx(tmp_path)
    shape_session = SimpleNamespace(
        get_inputs=lambda: [SimpleNamespace(name="images")],
        run=lambda *_args, **_kwargs: [np.zeros((1, 2), dtype=np.float32)],
    )
    drift_session = SimpleNamespace(
        get_inputs=lambda: [SimpleNamespace(name="images")],
        run=lambda *_args, **_kwargs: [np.ones((1, 1), dtype=np.float32)],
    )
    fake_ort_shape = SimpleNamespace(InferenceSession=lambda *_args, **_kwargs: shape_session)
    fake_ort_drift = SimpleNamespace(InferenceSession=lambda *_args, **_kwargs: drift_session)

    with (
        patch(
            "fovux.tools.export_onnx._forward_pytorch",
            return_value=[np.zeros((1, 1), dtype=np.float32)],
        ),
        patch("importlib.import_module", return_value=fake_ort_shape),
    ):
        with pytest.raises(FovuxExportParityError, match="shape mismatch"):
            _check_parity(pt, onnx, ExportOnnxInput(checkpoint=str(pt)))

    with (
        patch(
            "fovux.tools.export_onnx._forward_pytorch",
            return_value=[np.zeros((1, 1), dtype=np.float32)],
        ),
        patch("importlib.import_module", return_value=fake_ort_drift),
    ):
        passed, max_diff = _check_parity(pt, onnx, ExportOnnxInput(checkpoint=str(pt)))

    assert passed is False
    assert max_diff == pytest.approx(1.0)


def test_flatten_outputs_handles_tensor_lists_and_dicts():
    """Parity output flattening should normalize common model output containers."""
    fake_tensor = SimpleNamespace(
        detach=lambda: SimpleNamespace(cpu=lambda: SimpleNamespace(numpy=lambda: np.array([1.0])))
    )

    flattened = _flatten_outputs({"a": [fake_tensor], "b": (np.array([2.0]),)})

    assert len(flattened) == 2
    assert np.asarray(flattened[0]).tolist() == [1.0]
    assert np.asarray(flattened[1]).tolist() == [2.0]


# ── export_tflite ─────────────────────────────────────────────────────────────


def test_export_tflite_returns_output(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path)
    tflite = tmp_path / "best.tflite"
    tflite.write_bytes(b"t" * 256)

    with patch("fovux.tools.export_tflite._yolo_export_tflite", return_value=tflite):
        out = _run_export_tflite(ExportTfliteInput(checkpoint=str(pt)))

    assert out.tflite_path == tflite
    assert out.model_size_bytes == 256


def test_export_tflite_missing_checkpoint_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    with pytest.raises(FovuxCheckpointNotFoundError):
        _run_export_tflite(ExportTfliteInput(checkpoint="/no/model.pt"))


# ── quantize_int8 ─────────────────────────────────────────────────────────────


def test_quantize_int8_missing_dataset_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path)
    with pytest.raises(FovuxDatasetNotFoundError):
        _run_quantize_int8(
            QuantizeInt8Input(
                checkpoint=str(pt),
                calibration_dataset=Path("/no/dataset"),
            )
        )


def test_quantize_int8_requires_enough_calibration_images(tmp_path, monkeypatch):
    """INT8 quantization should reject undersized calibration datasets."""
    ckpt = tmp_path / "model.pt"
    ckpt.write_bytes(b"weights")
    dataset = tmp_path / "calib"
    images = dataset / "images" / "train"
    images.mkdir(parents=True)
    (dataset / "data.yaml").write_text("path: .\ntrain: images/train\nnames: [thing]\n")
    for index in range(3):
        (images / f"{index}.jpg").write_bytes(b"not really an image")

    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))

    with pytest.raises(FovuxDatasetEmptyError, match="INT8 calibration"):
        _run_quantize_int8(QuantizeInt8Input(checkpoint=str(ckpt), calibration_dataset=dataset))


def test_quantize_int8_returns_output(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt = _make_pt(tmp_path, size=2048)
    quant = tmp_path / "quant.onnx"
    quant.write_bytes(b"q" * 512)
    calibration_dataset = tmp_path / "calibration"
    calibration_images = calibration_dataset / "images" / "train"
    calibration_images.mkdir(parents=True)
    (calibration_dataset / "data.yaml").write_text(
        "path: .\ntrain: images/train\nnames: [thing]\n",
        encoding="utf-8",
    )
    for index in range(50):
        (calibration_images / f"{index}.jpg").write_bytes(b"image")

    with patch("fovux.tools.quantize_int8._yolo_quantize_int8", return_value=quant):
        out = _run_quantize_int8(
            QuantizeInt8Input(
                checkpoint=str(pt),
                calibration_dataset=calibration_dataset,
            )
        )

    assert out.quantized_path == quant
    assert out.size_reduction_pct == pytest.approx(75.0)


# ── quantize_report ───────────────────────────────────────────────────────────


def test_quantize_report_computes_delta(tmp_path, monkeypatch):
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    pt_orig = _make_pt(tmp_path, "orig.pt", size=4096)
    pt_quant = _make_pt(tmp_path, "quant.pt", size=1024)

    from types import SimpleNamespace

    def _fake_eval(inp):
        map50 = 0.75 if "orig" in inp.checkpoint else 0.72
        return SimpleNamespace(
            map50=map50,
            map50_95=map50 - 0.1,
            precision=0.8,
            recall=0.75,
            per_class=[],
            eval_duration_seconds=0.1,
        )

    with patch("fovux.tools.quantize_report._run_eval", side_effect=_fake_eval):
        out = _run_quantize_report(
            QuantizeReportInput(
                original_checkpoint=str(pt_orig),
                quantized_checkpoint=str(pt_quant),
                dataset_path=FIXTURES / "mini_yolo",
            )
        )

    assert abs(out.map50_delta - (-0.03)) < 1e-6
    assert out.size_reduction_pct == pytest.approx(75.0)
