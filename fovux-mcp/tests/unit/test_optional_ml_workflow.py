"""Contract tests for Torch 2.13 optional-ML compatibility automation."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PYPROJECT = ROOT / "fovux-mcp" / "pyproject.toml"
LOCKFILE = ROOT / "fovux-mcp" / "uv.lock"
WORKFLOW = ROOT / ".github" / "workflows" / "nightly-compat.yml"
OSV_CONFIG = ROOT / "fovux-mcp" / "osv-scanner.toml"
TESTING_DOC = ROOT / "docs" / "testing.md"


def test_yolo_extra_declares_validated_torch_stack() -> None:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    yolo = config["project"]["optional-dependencies"]["yolo"]
    if "torch>=2.13,<2.14" not in yolo:
        raise AssertionError('"torch>=2.13,<2.14" not found in yolo extra')
    if "torchvision>=0.28,<0.29" not in yolo:
        raise AssertionError('"torchvision>=0.28,<0.29" not found in yolo extra')
    if config["tool"]["uv"]["index"][0]["name"] != "pytorch-cpu":
        raise AssertionError('uv index[0]["name"] is not "pytorch-cpu"')


def test_lock_uses_torch_213_setuptools_83_and_no_cuda_runtime() -> None:
    lock = LOCKFILE.read_text(encoding="utf-8")
    if 'name = "torch"\nversion = "2.13.0+cpu"' not in lock:
        raise AssertionError("torch 2.13.0+cpu not found in lockfile")
    if 'name = "torchvision"\nversion = "0.28.0+cpu"' not in lock:
        raise AssertionError("torchvision 0.28.0+cpu not found in lockfile")
    if 'name = "setuptools"\nversion = "84.0.0"' not in lock:
        raise AssertionError("setuptools 84.0.0 not found in lockfile")
    if 'name = "triton"' in lock:
        raise AssertionError("triton found in lockfile (should not be present)")
    if 'name = "nvidia-cuda-runtime' in lock:
        raise AssertionError("nvidia-cuda-runtime found in lockfile (should not be present)")


def test_temporary_osv_exceptions_are_removed() -> None:
    config = OSV_CONFIG.read_text(encoding="utf-8")
    if "GHSA-h35f-9h28-mq5c" in config:
        raise AssertionError("GHSA-h35f-9h28-mq5c exception still present in osv-scanner.toml")
    if "GHSA-rrmf-rvhw-rf47" in config:
        raise AssertionError("GHSA-rrmf-rvhw-rf47 exception still present in osv-scanner.toml")


def test_nightly_workflow_covers_supported_platforms_and_real_smoke() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for runner in ("ubuntu-24.04", "macos-15", "windows-2022"):
        if runner not in workflow:
            raise AssertionError(f"Runner {runner} not found in workflow")
    if "FOVUX_TEST_OPTIONAL_ML" not in workflow:
        raise AssertionError("FOVUX_TEST_OPTIONAL_ML not found in workflow")
    if "FOVUX_TEST_YOLO_E2E" not in workflow:
        raise AssertionError("FOVUX_TEST_YOLO_E2E not found in workflow")
    if "test_optional_ml_stack.py" not in workflow:
        raise AssertionError("test_optional_ml_stack.py not found in workflow")
    if "persist-credentials: false" not in workflow:
        raise AssertionError("persist-credentials: false not found in workflow")
    if "--no-install-project --no-build" not in workflow:
        raise AssertionError("--no-install-project --no-build not found in workflow")
    if "--reinstall --no-deps --only-binary :all: opencv-python-headless" not in workflow:
        msg = (
            "--reinstall --no-deps --only-binary :all: opencv-python-headless not found in workflow"
        )
        raise AssertionError(msg)
    if "YOLO_CONFIG_DIR: ${{ runner.temp }}/ultralytics" not in workflow:
        raise AssertionError("YOLO_CONFIG_DIR not found in workflow")


def test_optional_ml_compatibility_is_documented() -> None:
    docs = TESTING_DOC.read_text(encoding="utf-8")
    if "Torch `2.13.x`" not in docs:
        raise AssertionError("Torch `2.13.x` not documented in testing.md")
    if "FOVUX_TEST_YOLO_E2E=1" not in docs:
        raise AssertionError("FOVUX_TEST_YOLO_E2E=1 not documented in testing.md")
    if "torch.cuda.is_available()" not in docs:
        raise AssertionError("torch.cuda.is_available() not documented in testing.md")
