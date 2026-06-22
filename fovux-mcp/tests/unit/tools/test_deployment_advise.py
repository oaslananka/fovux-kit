from __future__ import annotations

import pytest

from fovux.core.errors import FovuxCheckpointNotFoundError
from fovux.core.paths import ensure_fovux_dirs
from fovux.schemas.management import DeploymentAdviseInput
from fovux.tools.deployment_advise import _run_deployment_advise


def test_deployment_advise_unsupported_model_raises(tmp_path, monkeypatch):
    """Test that missing model files raise FovuxCheckpointNotFoundError."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    ensure_fovux_dirs(tmp_path)

    inp = DeploymentAdviseInput(
        model_path="nonexistent.pt",
        target_profile="cpu_server",
    )
    with pytest.raises(FovuxCheckpointNotFoundError):
        _run_deployment_advise(inp)


def test_deployment_advise_pytorch_profile_compat(tmp_path, monkeypatch):
    """Test compatibility rules, score calculations, and report generation for .pt models."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    ensure_fovux_dirs(tmp_path)

    # Create dummy .pt file
    pt_file = tmp_path / "best.pt"
    pt_file.write_text("dummy pytorch weights", encoding="utf-8")

    # 1. Target = cpu_server (compatible)
    inp_server = DeploymentAdviseInput(
        model_path=str(pt_file),
        target_profile="cpu_server",
    )
    out_server = _run_deployment_advise(inp_server)
    assert out_server.format == "pytorch"
    assert out_server.compatibility_preflight["compatible"] is True
    assert out_server.readiness_score == 100
    assert out_server.report_path.exists()
    assert "# Fovux Deployment Readiness Report" in out_server.report_path.read_text(
        encoding="utf-8"
    )

    # 2. Target = android_tflite (incompatible for .pt)
    inp_edge = DeploymentAdviseInput(
        model_path=str(pt_file),
        target_profile="android_tflite",
    )
    out_edge = _run_deployment_advise(inp_edge)
    assert out_edge.compatibility_preflight["compatible"] is False
    # compatibility deduction (-40) + format deduction (-15) = score 45
    assert out_edge.readiness_score == 45
    assert len(out_edge.risk_warnings) > 0
    assert any("not TFLite" in w for w in out_edge.risk_warnings)


def test_deployment_advise_onnx_profile_compat(tmp_path, monkeypatch):
    """Test compatibility and benchmarking checks for .onnx models."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    ensure_fovux_dirs(tmp_path)

    # Create dummy .onnx file
    onnx_file = tmp_path / "model.onnx"
    onnx_file.write_text("dummy onnx weights", encoding="utf-8")

    # 1. Target = browser_wasm (compatible)
    inp_wasm = DeploymentAdviseInput(
        model_path=str(onnx_file),
        target_profile="browser_wasm",
    )
    out_wasm = _run_deployment_advise(inp_wasm)
    assert out_wasm.format == "onnx"
    assert out_wasm.compatibility_preflight["compatible"] is True
    assert out_wasm.readiness_score == 100
    assert "onnxruntime" in out_wasm.runtime_snippets["python"]

    # 2. Target = android_tflite (incompatible for .onnx)
    inp_tflite = DeploymentAdviseInput(
        model_path=str(onnx_file),
        target_profile="android_tflite",
    )
    out_tflite = _run_deployment_advise(inp_tflite)
    assert out_tflite.compatibility_preflight["compatible"] is False
    assert any("TFLite format" in w for w in out_tflite.risk_warnings)


def test_deployment_advise_tflite_profile_compat(tmp_path, monkeypatch):
    """Test TFLite compatibility profile behavior."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    ensure_fovux_dirs(tmp_path)

    # Create dummy .tflite file
    tflite_file = tmp_path / "model.tflite"
    tflite_file.write_text("dummy tflite weights", encoding="utf-8")

    inp = DeploymentAdviseInput(
        model_path=str(tflite_file),
        target_profile="android_tflite",
    )
    out = _run_deployment_advise(inp)
    assert out.format == "tflite"
    assert out.compatibility_preflight["compatible"] is True
    assert "tflite" in out.runtime_snippets["python"]
    assert "tflite" in out.runtime_snippets["docker"]


def test_deployment_advise_tensorrt_profile_compat(tmp_path, monkeypatch):
    """Test TensorRT compatibility profile behavior."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path))
    ensure_fovux_dirs(tmp_path)

    # Create dummy .engine file
    engine_file = tmp_path / "model.engine"
    engine_file.write_text("dummy tensorrt engine", encoding="utf-8")

    inp = DeploymentAdviseInput(
        model_path=str(engine_file),
        target_profile="nvidia_gpu_tensorrt",
    )
    out = _run_deployment_advise(inp)
    assert out.format == "tensorrt"
    assert out.compatibility_preflight["compatible"] is True
    assert "nvidia_gpu_tensorrt" in out.target_profile
