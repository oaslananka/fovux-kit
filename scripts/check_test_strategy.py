"""Fail-fast checks for the repository test strategy contract."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP_ROOT = ROOT / "fovux-mcp"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def _coverage_omits() -> list[str]:
    data = tomllib.loads(_read(MCP_ROOT / "pyproject.toml"))
    return [str(item) for item in data["tool"]["coverage"]["run"]["omit"]]


def _has_scheduled_workflow(path: Path) -> bool:
    content = _read(path)
    return "schedule:" in content and "cron:" in content


def main() -> int:
    """Verify that quality issue #70 acceptance criteria stay represented in code/docs."""
    failures: list[str] = []

    golden = _read(MCP_ROOT / "tests" / "unit" / "tools" / "test_golden_dataset.py")
    for phrase in [
        "golden_dataset_path",
        "Unicode folder names",
        "Corrupt images",
        "Missing labels",
        "Train/val leakage",
        "Class mismatch",
        "Windows path slashes",
        "_create_unique_image",
    ]:
        _expect(
            phrase in golden,
            f"Golden dataset test is missing deterministic edge-case marker: {phrase}",
            failures,
        )

    pipeline = _read(
        MCP_ROOT / "tests" / "integration" / "test_pipeline_integration.py"
    )
    for phrase in [
        "test_export_onnx_and_tflite_contract",
        "test_inference_and_rtsp_pipeline_contract",
        "test_train_worker_integration_flow",
        "_run_export_onnx",
        "_run_export_tflite",
        "_run_infer_rtsp",
    ]:
        _expect(
            phrase in pipeline,
            f"Runtime/export/inference pipeline coverage marker missing: {phrase}",
            failures,
        )

    train_worker = _read(MCP_ROOT / "tests" / "unit" / "test_train_worker.py")
    _expect(
        "fovux.core.train_worker" in train_worker
        and "runpy.run_module" in train_worker,
        "Detached training worker subprocess/module coverage is missing.",
        failures,
    )

    taskfile = _read(ROOT / "Taskfile.yml")
    for phrase in [
        "test:fast:",
        "not slow and not integration and not network and not gpu",
        "test:cov:",
    ]:
        _expect(
            phrase in taskfile, f"Taskfile test lane marker missing: {phrase}", failures
        )

    nightly = ROOT / ".github" / "workflows" / "nightly-compat.yml"
    mutation = ROOT / ".github" / "workflows" / "mutation.yml"
    _expect(
        _has_scheduled_workflow(nightly),
        "Nightly compatibility workflow is not scheduled.",
        failures,
    )
    _expect(
        _has_scheduled_workflow(mutation),
        "Mutation workflow is not scheduled.",
        failures,
    )
    _expect(
        "run_mutmut.py run" in _read(mutation),
        "Mutation workflow does not run mutmut.",
        failures,
    )

    benchmarks = _read(MCP_ROOT / "tests" / "bench" / "test_dataset_benchmarks.py")
    for phrase in ["benchmark", "_run_inspect", "_run_find_duplicates"]:
        _expect(
            phrase in benchmarks,
            f"Performance benchmark marker missing: {phrase}",
            failures,
        )

    coverage_doc = _read(MCP_ROOT / "docs" / "testing-and-coverage.md")
    for omitted in _coverage_omits():
        if omitted == "tests/*":
            continue
        _expect(
            f"`{omitted}`" in coverage_doc,
            f"Coverage omit pattern lacks documented rationale: {omitted}",
            failures,
        )
    _expect(
        "minimum 85% required" in coverage_doc,
        "Coverage policy doc must match the configured --cov-fail-under=85 gate.",
        failures,
    )

    for phrase in [
        "Golden Dataset Contract",
        "Runtime and Export Contract Coverage",
        "Fast PR Checks",
        "Nightly / Scheduled Checks",
        "Mutation Testing Gate",
        "Performance Baselines",
        "Coverage Signals and Merge Authority",
        "ci-required",
        "Codecov flag/component `backend`",
        "Codecov flag/component `studio`",
        "80% target",
        "85% target",
        "1% tolerance",
        "45% Studio line-coverage floor",
        "truthful ratchet baseline",
        "Automatic Analysis was disabled",
        "scripts/check_coverage_reports.py",
    ]:
        _expect(
            phrase in coverage_doc,
            f"Testing policy doc section missing: {phrase}",
            failures,
        )

    stale_percent = re.search(r"minimum 90% required", coverage_doc)
    _expect(
        stale_percent is None,
        "Coverage policy still mentions stale 90% threshold.",
        failures,
    )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print(
        "Test strategy checks passed: golden dataset, runtime contracts, nightly/mutation, benchmarks, and coverage rationales are documented and enforced."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
