"""Contract tests for Torch 2.13 optional-ML compatibility automation."""

from __future__ import annotations

import re
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
    assert "torch>=2.13,<2.14" in yolo
    assert "torchvision>=0.28,<0.29" in yolo
    assert config["tool"]["uv"]["index"][0]["name"] == "pytorch-cpu"


def _assert_supported_setuptools_lock(lock: str) -> None:
    """Keep the 83.0.0 compatibility floor without pinning a transitive lock entry."""
    packages = tomllib.loads(lock)["package"]
    versions = [p["version"] for p in packages if p["name"] == "setuptools"]
    if len(versions) != 1:
        raise AssertionError("Expected one resolved setuptools package")
    version = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", versions[0])
    if version is None:
        raise AssertionError("Expected a stable setuptools release")
    if tuple(map(int, version.groups())) < (83, 0, 0):
        raise AssertionError("Expected setuptools >=83.0.0")


def test_lock_uses_torch_213_supported_setuptools_and_no_cuda_runtime() -> None:
    lock = LOCKFILE.read_text(encoding="utf-8")
    assert 'name = "torch"\nversion = "2.13.0+cpu"' in lock
    assert 'name = "torchvision"\nversion = "0.28.0+cpu"' in lock
    _assert_supported_setuptools_lock(lock)
    assert 'name = "triton"' not in lock
    assert 'name = "nvidia-cuda-runtime' not in lock


def test_setuptools_lock_contract_rejects_missing_or_unsupported_versions() -> None:
    for version in ("82.0.1", "84.0.0rc1"):
        try:
            _assert_supported_setuptools_lock(
                f'[[package]]\nname = "setuptools"\nversion = "{version}"\n'
            )
        except AssertionError:
            continue
        raise AssertionError(f"setuptools {version} should not pass the compatibility gate")

    for version in ("83.0.0", "84.2.1"):
        _assert_supported_setuptools_lock(
            f'[[package]]\nname = "setuptools"\nversion = "{version}"\n'
        )


def test_temporary_osv_exceptions_are_removed() -> None:
    config = OSV_CONFIG.read_text(encoding="utf-8")
    assert "GHSA-h35f-9h28-mq5c" not in config
    assert "GHSA-rrmf-rvhw-rf47" not in config


def test_nightly_workflow_covers_supported_platforms_and_real_smoke() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for runner in ("ubuntu-24.04", "macos-15", "windows-2022"):
        assert runner in workflow
    assert "FOVUX_TEST_OPTIONAL_ML" in workflow
    assert "FOVUX_TEST_YOLO_E2E" in workflow
    assert "test_optional_ml_stack.py" in workflow
    assert "persist-credentials: false" in workflow
    assert "--no-install-project --no-build" in workflow
    assert "--reinstall --no-deps --only-binary :all: opencv-python-headless" in workflow
    assert "YOLO_CONFIG_DIR: ${{ runner.temp }}/ultralytics" in workflow


def test_optional_ml_compatibility_is_documented() -> None:
    docs = TESTING_DOC.read_text(encoding="utf-8")
    assert "Torch `2.13.x`" in docs
    assert "FOVUX_TEST_YOLO_E2E=1" in docs
    assert "torch.cuda.is_available()" in docs
