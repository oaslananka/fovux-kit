"""Contract tests for Codecov and workflow-security observability."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_codecov_policy_is_nonduplicative_and_component_aware() -> None:
    config = yaml.safe_load((ROOT / "codecov.yml").read_text(encoding="utf-8"))

    project = config["coverage"]["status"]["project"]["default"]
    patch = config["coverage"]["status"]["patch"]["default"]
    for status in (project, patch):
        assert status["target"] == "auto"
        assert status["threshold"] == "1%"
        assert status["informational"] is True

    assert set(config["flags"]) == {"backend", "studio"}
    components = config["component_management"]["individual_components"]
    assert {item["component_id"] for item in components} == {"backend", "studio"}
    assert config["bundle_analysis"]["status"] == "informational"


def test_quality_lane_uploads_coverage_and_failed_test_reports_once() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert workflow.count("codecov/codecov-action@fb8b3582c8e4def4969c97caa2f19720cb33a72f") == 4
    assert workflow.count("use_oidc: true") == 4
    assert "id-token: write" in workflow
    assert "fovux-mcp/coverage.xml" in workflow
    assert "fovux-studio/coverage/lcov.info" in workflow
    assert "fovux-mcp/junit.xml" in workflow
    assert "fovux-studio/coverage/junit.xml" in workflow
    assert workflow.count("report_type: test_results") == 2
    assert "continue-on-error: true" in workflow
    assert "Confirm deterministic quality gate passed" in workflow


def test_zizmor_is_in_precommit_and_ci_parity() -> None:
    precommit = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    taskfile = (ROOT / "Taskfile.yml").read_text(encoding="utf-8")

    assert "zizmorcore/zizmor-pre-commit" in precommit
    assert "rev: v1.27.0" in precommit
    assert taskfile.count("uvx zizmor==1.27.0") >= 2
