"""Contract tests for the required CI lane topology."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _job_block(text: str, job: str, next_job: str | None) -> str:
    start = text.index(f"  {job}:\n")
    end = text.index(f"  {next_job}:\n", start) if next_job else len(text)
    return text[start:end]


def test_ci_has_one_full_quality_lane() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    quality = _job_block(workflow, "quality", "compatibility")

    assert "runs-on: ubuntu-24.04" in quality
    assert 'python-version: "3.12"' in quality
    assert 'node-version: "24.16.0"' in quality
    assert "run: task ci" in quality


def test_compatibility_lane_is_python_os_smoke_only() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    compatibility = _job_block(workflow, "compatibility", "compatibility-required")

    assert "os: [ubuntu-24.04, macos-15, windows-2022]" in compatibility
    assert 'python-version: ["3.12", "3.13", "3.14"]' in compatibility
    assert "node-version:" not in compatibility
    assert "task ci" not in compatibility
    assert "task security" not in compatibility
    assert "task docs" not in compatibility
    assert "release:dry-run" not in compatibility
    assert "tests/unit/test_paths.py" in compatibility
    assert "tests/unit/test_processes.py" in compatibility
    assert "uv build --wheel" in compatibility


def test_node_compatibility_is_a_separate_ubuntu_lane() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    node = _job_block(workflow, "node-compatibility", "node-required")

    assert 'node-version: ["22", "24.16.0"]' in node
    assert "runs-on: ubuntu-24.04" in node
    assert "pnpm-lock.yaml" in node
    assert "package-lock.json" in node
    assert "pnpm run typecheck" in node
    assert "pnpm test" in node
    assert "npm pack --dry-run" in node


def test_required_aggregate_depends_on_lane_summaries() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    required = _job_block(workflow, "ci-required", None)

    assert "quality" in required
    assert "compatibility-required" in required
    assert "node-required" in required
    assert "renovate-config" in required
    assert "needs.quality.result" in required
    assert "needs.compatibility-required.result" in required
    assert "needs.node-required.result" in required


def test_slow_validation_is_scheduled_not_a_pr_requirement() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    slow = _job_block(workflow, "slow-validation", "renovate-config")
    required = _job_block(workflow, "ci-required", None)

    assert "github.event_name == 'schedule'" in slow
    assert "inputs.run_slow == 'true'" in slow
    assert "slow-validation" not in required.split("needs:", 1)[1].split("if:", 1)[0]


def test_pr_concurrency_cancels_superseded_runs() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "github.event.pull_request.number || github.ref" in workflow
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in workflow


def test_pnpm_cache_is_initialized_after_pnpm_installation() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    quality = _job_block(workflow, "quality", "compatibility")
    node = _job_block(workflow, "node-compatibility", "node-required")

    assert "cache: pnpm" not in quality + node
    assert quality.index("Install quality tools") < quality.index("actions/cache@")
    assert node.index("Install pnpm") < node.index("actions/cache@")
    assert "matrix.node-version" in node
    assert "fovux-studio/pnpm-lock.yaml" in node
    assert "fovux-mcp-npm/package-lock.json" in node


def test_compatibility_installs_are_frozen_without_implicit_builds() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    compatibility = _job_block(workflow, "compatibility", "compatibility-required")
    node = _job_block(workflow, "node-compatibility", "node-required")
    slow = _job_block(workflow, "slow-validation", "renovate-config")

    wheel_only_sync = "uv sync --frozen --extra dev --no-install-project --no-build"
    assert wheel_only_sync in compatibility
    assert "matrix.os == 'macos-15' && matrix.python-version == '3.14'" in compatibility
    assert "--no-build-package fovux-mcp # NOSONAR" in compatibility
    assert "uv run --no-sync --no-build python" in compatibility
    assert "uv run --no-sync --no-build pytest" in compatibility
    assert "pnpm install --frozen-lockfile --ignore-scripts" in node
    assert "pnpm rebuild esbuild" in node
    assert wheel_only_sync in slow
    assert "uv run --no-sync --no-build pytest" in slow
