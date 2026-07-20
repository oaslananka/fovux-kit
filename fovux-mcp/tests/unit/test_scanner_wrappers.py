"""Tests for credential-aware local scanner wrappers."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_snyk  # noqa: E402
import run_sonar  # noqa: E402
import scanner_runner  # noqa: E402


def test_missing_executable_is_explicit_skip(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setattr(scanner_runner.shutil, "which", lambda _name: None)

    result = scanner_runner.run_scanner(
        name="Example",
        command=("snyk", "test"),
        token_names=(),
        required=False,
        environ={},
    )

    assert result == 0
    assert "SKIP: Example executable 'snyk' is not installed" in capsys.readouterr().out


def test_missing_token_can_be_required(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setattr(scanner_runner.shutil, "which", lambda _name: "/usr/bin/snyk")

    result = scanner_runner.run_scanner(
        name="Example",
        command=("snyk", "test"),
        token_names=("EXAMPLE_TOKEN",),
        required=True,
        environ={},
    )

    assert result == scanner_runner.NOT_CONFIGURED_EXIT
    assert "ERROR: Example requires EXAMPLE_TOKEN" in capsys.readouterr().out


def test_scanner_exit_code_is_propagated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scanner_runner.shutil, "which", lambda _name: "/usr/bin/snyk")
    observed: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 23)

    monkeypatch.setattr(scanner_runner.subprocess, "run", fake_run)

    result = scanner_runner.run_scanner(
        name="Example",
        command=("snyk", "test", "--flag"),
        token_names=("EXAMPLE_TOKEN",),
        required=False,
        environ={"EXAMPLE_TOKEN": "top-secret"},
        cwd=REPO_ROOT,
    )

    assert result == 23
    assert observed["command"] == ["/usr/bin/snyk", "test", "--flag"]
    assert observed["kwargs"] == {
        "check": False,
        "cwd": REPO_ROOT,
        "env": {"EXAMPLE_TOKEN": "top-secret"},
        "text": True,
    }


def test_display_command_redacts_environment_tokens() -> None:
    rendered = scanner_runner.format_command(
        ("snyk", "--header", "Bearer top-secret"),
        environ={"EXAMPLE_TOKEN": "top-secret"},
        token_names=("EXAMPLE_TOKEN",),
    )

    assert "top-secret" not in rendered
    assert "[REDACTED]" in rendered


def test_unapproved_scanner_executable_is_rejected() -> None:
    with pytest.raises(ValueError, match="not approved"):
        scanner_runner.run_scanner(
            name="Example",
            command=("bash", "-c", "echo unsafe"),
            token_names=(),
            required=False,
            environ={},
        )


def test_multiline_scanner_argument_is_rejected() -> None:
    with pytest.raises(ValueError, match="printable single-line"):
        scanner_runner.run_scanner(
            name="Example",
            command=("snyk", "test\nsecond-command"),
            token_names=(),
            required=False,
            environ={},
        )


def test_snyk_runs_open_source_then_code(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_run_scanner(**kwargs: object) -> int:
        command = kwargs["command"]
        assert isinstance(command, tuple)
        calls.append(command)
        return 0

    monkeypatch.setattr(run_snyk, "run_scanner", fake_run_scanner)

    assert run_snyk.main([]) == 0
    assert calls == [
        ("snyk", "test", "--all-projects", "--severity-threshold=high"),
        ("snyk", "code", "test", "--severity-threshold=high"),
    ]


def test_sonar_builds_branch_analysis_command(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[list[str]] = []

    def fake_run_scanner(**kwargs: object) -> int:
        command = kwargs["command"]
        assert isinstance(command, list)
        observed.append(command)
        return 0

    monkeypatch.setattr(run_sonar, "run_scanner", fake_run_scanner)

    assert run_sonar.main(["--branch", "feature/security"]) == 0
    assert observed == [
        ["sonar-scanner", "-Dsonar.branch.name=feature/security"],
    ]


def test_sonar_uses_current_git_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[list[str]] = []

    def fake_run_scanner(**kwargs: object) -> int:
        command = kwargs["command"]
        assert isinstance(command, list)
        observed.append(command)
        return 0

    monkeypatch.setattr(run_sonar, "detect_current_branch", lambda _parser: "feature/auto")
    monkeypatch.setattr(run_sonar, "run_scanner", fake_run_scanner)

    assert run_sonar.main([]) == 0
    assert observed == [["sonar-scanner", "-Dsonar.branch.name=feature/auto"]]


def test_sonar_builds_pull_request_analysis_command(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: list[list[str]] = []

    def fake_run_scanner(**kwargs: object) -> int:
        command = kwargs["command"]
        assert isinstance(command, list)
        observed.append(command)
        return 0

    monkeypatch.setattr(run_sonar, "run_scanner", fake_run_scanner)

    assert (
        run_sonar.main(
            [
                "--branch",
                "feature/security",
                "--pull-request",
                "138",
                "--base",
                "main",
            ]
        )
        == 0
    )
    assert observed == [
        [
            "sonar-scanner",
            "-Dsonar.pullrequest.key=138",
            "-Dsonar.pullrequest.branch=feature/security",
            "-Dsonar.pullrequest.base=main",
        ],
    ]


def test_scanner_outputs_are_ignored() -> None:
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

    for ignored in (
        ".scanner-cache/",
        ".sonar/",
        ".sonar-scanner/",
        ".semgrep-cache/",
        "semgrep-results.sarif",
        "snyk-results.json",
    ):
        assert ignored in gitignore


def test_taskfile_and_pre_commit_use_shared_wrappers() -> None:
    taskfile = (REPO_ROOT / "Taskfile.yml").read_text(encoding="utf-8")
    pre_commit = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "security:semgrep:" in taskfile
    assert "security:snyk:" in taskfile
    assert "security:sonar:" in taskfile
    assert "python scripts/run_snyk.py" in taskfile
    assert "python scripts/run_sonar.py" in taskfile
    assert "id: snyk-maintainer" in pre_commit
    assert "entry: python scripts/run_snyk.py" in pre_commit
    assert "stages: [pre-push, manual]" in pre_commit
    assert "id: sonar-maintainer" in pre_commit
    assert "entry: python scripts/run_sonar.py" in pre_commit
    assert "stages: [manual]" in pre_commit


def test_sonar_project_properties_scope_sources_and_reports() -> None:
    properties = (REPO_ROOT / "sonar-project.properties").read_text(encoding="utf-8")

    assert "sonar.projectKey=oaslananka_fovux-kit" in properties
    assert "sonar.organization=oaslananka" in properties
    assert "sonar.sources=fovux-mcp/src,fovux-studio/src,fovux-mcp-npm/bin" in properties
    assert "sonar.tests=fovux-mcp/tests,fovux-studio/test" in properties
    assert "sonar.python.coverage.reportPaths=fovux-mcp/coverage.xml" in properties
    assert "sonar.javascript.lcov.reportPaths=fovux-studio/coverage/lcov.info" in properties
