"""Tests for safe local scanner wrappers."""

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

import run_sonar  # noqa: E402
import scanner_runner  # noqa: E402


def test_missing_executable_is_explicit_skip(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setattr(scanner_runner.shutil, "which", lambda _name: None)

    result = scanner_runner.run_scanner(
        name="Example",
        command=("osv-scanner", "scan", "source"),
        token_names=(),
        required=False,
        environ={},
    )

    assert result == 0
    assert "SKIP: Example executable 'osv-scanner' is not installed" in capsys.readouterr().out


def test_missing_token_can_be_required(monkeypatch: pytest.MonkeyPatch, capsys: Any) -> None:
    monkeypatch.setattr(scanner_runner.shutil, "which", lambda _name: "/usr/bin/sonar-scanner")

    result = scanner_runner.run_scanner(
        name="Example",
        command=("sonar-scanner", "-Dsonar.branch.name=main"),
        token_names=("EXAMPLE_TOKEN",),
        required=True,
        environ={},
    )

    assert result == scanner_runner.NOT_CONFIGURED_EXIT
    assert "ERROR: Example requires EXAMPLE_TOKEN" in capsys.readouterr().out


def test_scanner_exit_code_is_propagated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scanner_runner.shutil, "which", lambda _name: "/usr/bin/osv-scanner")
    observed: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 23)

    monkeypatch.setattr(scanner_runner.subprocess, "run", fake_run)

    result = scanner_runner.run_scanner(
        name="Example",
        command=("osv-scanner", "scan", "source", "--verbosity=error"),
        token_names=(),
        required=False,
        environ={},
        cwd=REPO_ROOT,
    )

    assert result == 23
    assert observed["command"] == ["/usr/bin/osv-scanner", "scan", "source", "--verbosity=error"]
    assert observed["kwargs"] == {
        "check": False,
        "cwd": REPO_ROOT,
        "env": {},
        "text": True,
    }


def test_display_command_redacts_environment_tokens() -> None:
    rendered = scanner_runner.format_command(
        ("sonar-scanner", "-Dsonar.token=top-secret"),
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
            command=("osv-scanner", "scan\nsecond-command"),
            token_names=(),
            required=False,
            environ={},
        )


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
    ):
        assert ignored in gitignore


def test_taskfile_and_pre_commit_use_shared_wrappers() -> None:
    taskfile = (REPO_ROOT / "Taskfile.yml").read_text(encoding="utf-8")
    pre_commit = (REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "security:semgrep:" in taskfile
    assert "security:osv:" in taskfile
    assert "security:sonar:" in taskfile
    developer_block = taskfile.split("  security:developer:\n", 1)[1].split("\n  security:\n", 1)[0]
    matrix_security_block = taskfile.split("\n  security:\n", 1)[1].split(
        "\n  security:posture:\n", 1
    )[0]
    assert "task: security:semgrep" in developer_block
    assert "task: security:trivy" in developer_block
    assert "task: security:osv" in developer_block
    assert "task: security:semgrep" not in matrix_security_block
    assert "generate_security_posture.py" not in matrix_security_block
    posture_block = taskfile.split("  security:posture:\n", 1)[1].split(
        "\n  deps:renovate:validate:\n", 1
    )[0]
    assert "generate_security_posture.py --strict" in posture_block
    assert "python scripts/run_osv.py --required" in taskfile
    assert "python scripts/run_gitleaks.py --required" in taskfile
    assert "python scripts/run_trivy.py --required" in taskfile
    assert "python scripts/run_sonar.py" in taskfile
    assert "task: ci" in taskfile.split("  verify:required:\n", 1)[1]
    assert "id: osv-maintainer" in pre_commit
    assert "entry: python scripts/run_osv.py" in pre_commit
    assert "stages: [pre-push, manual]" in pre_commit
    assert "id: sonar-maintainer" in pre_commit
    assert "entry: python scripts/run_sonar.py" in pre_commit
    assert "stages: [manual]" in pre_commit
    assert "id: pre-push-checks" in pre_commit
    assert "id: ci-parity" not in pre_commit


def test_sonar_project_properties_scope_sources_and_reports() -> None:
    properties = (REPO_ROOT / "sonar-project.properties").read_text(encoding="utf-8")

    assert "sonar.projectKey=oaslananka_fovux-kit" in properties
    assert "sonar.organization=oaslananka" in properties
    assert "sonar.sources=fovux-mcp/src,fovux-studio/src,fovux-mcp-npm/bin" in properties
    assert "sonar.tests=fovux-mcp/tests,fovux-studio/test" in properties
    assert "sonar.python.coverage.reportPaths=fovux-mcp/coverage.xml" in properties
    assert "sonar.javascript.lcov.reportPaths=fovux-studio/coverage/lcov.info" in properties
    assert (
        "fovux-studio/src/fovux/tools/definitions.ts"
        in properties.split("sonar.cpd.exclusions=", 1)[1].splitlines()[0]
    )


def _load_run_trivy() -> Any:
    import importlib.util

    path = SCRIPTS_DIR / "run_trivy.py"
    spec = importlib.util.spec_from_file_location("run_trivy", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_trivy_wrapper_uses_ci_equivalent_filesystem_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_run_trivy()
    observed: list[dict[str, object]] = []

    def fake_run_scanner(**kwargs: object) -> int:
        observed.append(kwargs)
        return 0

    monkeypatch.setattr(module, "run_scanner", fake_run_scanner)
    monkeypatch.setattr(module, "verify_scanner_version", lambda **_kwargs: None)

    assert module.main(["--required"]) == 0
    assert observed == [
        {
            "name": "Trivy filesystem scan",
            "command": (
                "trivy",
                "fs",
                "--scanners=vuln",
                "--severity=CRITICAL,HIGH",
                "--ignore-unfixed",
                "--exit-code=1",
                ".",
            ),
            "token_names": (),
            "required": True,
            "cwd": REPO_ROOT,
        }
    ]


def test_trivy_is_an_approved_scanner_executable() -> None:
    assert "trivy" in scanner_runner._ALLOWED_EXECUTABLES  # noqa: SLF001


def test_shared_scanner_version_gate_rejects_drift(
    monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    monkeypatch.setattr(scanner_runner.shutil, "which", lambda _name: "/usr/bin/trivy")
    monkeypatch.setattr(
        scanner_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["trivy", "--version"], 0, stdout="Version: 0.69.0\n", stderr=""
        ),
    )

    assert (
        scanner_runner.verify_scanner_version(
            name="Trivy",
            executable="trivy",
            version_args=("--version",),
            expected_version="0.70.0",
            version_pattern=r"^Version:\s+([^\s]+)",
            required=True,
        )
        == scanner_runner.NOT_CONFIGURED_EXIT
    )
    assert "Trivy 0.70.0 is required" in capsys.readouterr().out


def _load_run_gitleaks() -> Any:
    import importlib.util

    path = SCRIPTS_DIR / "run_gitleaks.py"
    spec = importlib.util.spec_from_file_location("run_gitleaks", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gitleaks_wrapper_uses_ci_equivalent_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_run_gitleaks()
    observed: list[dict[str, object]] = []
    version_checks: list[dict[str, object]] = []

    monkeypatch.setattr(
        module, "verify_scanner_version", lambda **kwargs: version_checks.append(kwargs)
    )
    monkeypatch.setattr(module, "run_scanner", lambda **kwargs: observed.append(kwargs) or 0)

    assert module.main(["--required"]) == 0
    assert version_checks == [
        {
            "name": "Gitleaks",
            "executable": "gitleaks",
            "version_args": ("version",),
            "expected_version": "8.30.1",
            "version_pattern": r"^v?([0-9]+\.[0-9]+\.[0-9]+)\s*$",
            "required": True,
        }
    ]
    assert observed == [
        {
            "name": "Gitleaks secret scan",
            "command": ("gitleaks", "detect", "--no-banner", "--redact"),
            "token_names": (),
            "required": True,
            "cwd": REPO_ROOT,
        }
    ]


def test_bootstrap_pins_ci_equivalent_trivy() -> None:
    bootstrap = (REPO_ROOT / "scripts" / "bootstrap-dev.sh").read_text(encoding="utf-8")
    workflow = (REPO_ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")

    assert 'TRIVY_VERSION="v0.70.0"' in bootstrap
    assert "installed_go_tool_version()" in bootstrap
    assert "Replacing $command_name ${installed:-unknown} with pinned ${expected}" in bootstrap
    assert 'install -m 0755 "$built_binary" "${HOME}/.local/bin/${command_name}"' in bootstrap
    assert "trivy_${expected}_${os}-${arch}.tar.gz" in bootstrap
    assert "version: v0.70.0" in workflow


def test_ci_and_bootstrap_use_verified_gitleaks_release_binary() -> None:
    bootstrap = (REPO_ROOT / "scripts" / "bootstrap-dev.sh").read_text(encoding="utf-8")
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    security = (REPO_ROOT / ".github" / "workflows" / "security.yml").read_text(encoding="utf-8")

    go_install = "go install github.com/zricethezav/gitleaks/v8@v8.30.1"
    assert go_install not in ci
    assert "GITLEAKS_VERSION: 8.30.1" in ci
    assert "GITLEAKS_SHA256: 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb" in ci
    assert (
        "GITLEAKS_SHA256: 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"
        in security
    )
    assert "install_gitleaks()" in bootstrap
    assert "install_go_tool gitleaks " not in bootstrap
    assert "gitleaks_${expected}_${os}_${arch}.tar.gz" in bootstrap
    assert "gitleaks_${expected}_checksums.txt" in bootstrap
