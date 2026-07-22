"""Contract tests for coverage reporting and workflow-security observability."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_codecov_policy_is_nonduplicative_and_component_aware() -> None:
    config = yaml.safe_load((ROOT / "codecov.yml").read_text(encoding="utf-8"))

    codecov = config["codecov"]
    assert codecov["require_ci_to_pass"] is False
    assert codecov["notify"]["after_n_builds"] == 2
    assert codecov["notify"]["wait_for_ci"] is False
    assert codecov["notify"]["notify_error"] is True
    assert codecov["notify"]["manual_trigger"] is True
    assert config["github_checks"] is False
    assert config["comment"]["require_changes"] is False

    project = config["coverage"]["status"]["project"]["default"]
    patch = config["coverage"]["status"]["patch"]["default"]
    assert project["target"] == "80%"
    assert patch["target"] == "85%"
    for status in (project, patch):
        assert status["threshold"] == "1%"
        assert status["informational"] is False

    assert set(config["flags"]) == {"backend", "studio"}
    components = {
        item["component_id"]: item
        for item in config["component_management"]["individual_components"]
    }
    assert set(components) == {"backend", "studio"}
    assert components["backend"]["statuses"][0]["target"] == "85%"
    assert components["studio"]["statuses"][0]["target"] == "45%"
    assert all(
        component["statuses"][0]["informational"] is True for component in components.values()
    )
    expected_ignored = {
        "fovux-mcp/src/fovux/**/__main__.py",
        "fovux-mcp/src/fovux/**/cli.py",
        "fovux-mcp/src/fovux/core/dataset_utils.py",
        "fovux-mcp/src/fovux/core/train_worker.py",
        "fovux-mcp/src/fovux/core/ultralytics_adapter.py",
        "fovux-mcp/src/fovux/tools/demo_init.py",
        "fovux-mcp/src/fovux/tools/deployment_advise.py",
        "fovux-mcp/src/fovux/tools/export_tflite.py",
        "fovux-mcp/src/fovux/tools/infer_image.py",
        "fovux-mcp/src/fovux/tools/infer_rtsp.py",
        "fovux-mcp/src/fovux/tools/run_compare.py",
        "fovux-mcp/src/fovux/tools/sync_to_mlflow.py",
    }
    assert set(config["ignore"]) == expected_ignored
    sonar = (ROOT / "sonar-project.properties").read_text(encoding="utf-8")
    assert all(path in sonar for path in expected_ignored)
    assert config["bundle_analysis"]["status"] == "informational"


def test_quality_lane_validates_and_uploads_reports_once() -> None:
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert workflow.count("codecov/codecov-action@fb8b3582c8e4def4969c97caa2f19720cb33a72f") == 5
    assert workflow.count("use_oidc: true") == 5
    assert workflow.count("run_command: send-notifications") == 1
    assert "Finalize Codecov notifications" in workflow
    assert "id-token: write" in workflow
    assert "fovux-mcp/coverage.xml" in workflow
    assert "fovux-studio/coverage/lcov.info" in workflow
    assert "fovux-mcp/junit.xml" in workflow
    assert "fovux-studio/coverage/junit.xml" in workflow
    assert workflow.count("report_type: test_results") == 2
    assert "python scripts/check_coverage_reports.py" in workflow
    assert "--backend-minimum-percent 85" in workflow
    assert "--studio-minimum-percent 45" in workflow
    assert "SonarSource/sonarqube-scan-action@22918119ff8e1ca75a623e15c8296b6ea4fbe28f" in workflow
    assert "SONAR_TOKEN: ${{ secrets.SONAR_TOKEN }}" in workflow
    assert "continue-on-error: true" in workflow
    assert "Confirm deterministic quality gate passed" in workflow
    assert not (ROOT / ".github/workflows/sonar-analysis-migration.yml").exists()


def test_sonar_and_studio_coverage_policy_is_explicit() -> None:
    sonar = (ROOT / "sonar-project.properties").read_text(encoding="utf-8")
    package = json.loads((ROOT / "fovux-studio/package.json").read_text(encoding="utf-8"))

    assert "sonar.python.coverage.reportPaths=fovux-mcp/coverage.xml" in sonar
    assert "sonar.javascript.lcov.reportPaths=fovux-studio/coverage/lcov.info" in sonar
    assert "sonar.qualitygate.wait=true" in sonar
    assert "sonar.qualitygate.timeout=300" in sonar
    assert "--coverage.thresholds.lines=45" in package["scripts"]["coverage:ci"]
    assert "--coverage.exclude='test/**'" in package["scripts"]["coverage:ci"]


def test_zizmor_is_in_precommit_and_ci_parity() -> None:
    precommit = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    taskfile = (ROOT / "Taskfile.yml").read_text(encoding="utf-8")

    assert "zizmorcore/zizmor-pre-commit" in precommit
    assert "rev: v1.27.0" in precommit
    assert taskfile.count("uvx zizmor==1.27.0") >= 2
