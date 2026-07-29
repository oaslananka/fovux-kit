"""Regression tests for the credential-free OSV-Scanner security layer."""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
from packaging.version import Version

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
RUN_OSV = SCRIPTS / "run_osv.py"
SECURITY_WORKFLOW = ROOT / ".github" / "workflows" / "security.yml"
OSV_ACTION_SHA = "9a498708959aeaef5ef730655706c5a1df1edbc2"
STUDIO_PACKAGE = ROOT / "fovux-studio" / "package.json"
UV_LOCK = ROOT / "fovux-mcp" / "uv.lock"
LOCKFILES = (
    "fovux-mcp/uv.lock",
    "fovux-studio/pnpm-lock.yaml",
    "fovux-mcp-npm/package-lock.json",
)

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import scanner_runner  # noqa: E402


def _load_run_osv() -> ModuleType:
    assert RUN_OSV.is_file(), "credential-free OSV wrapper is missing"
    spec = importlib.util.spec_from_file_location("run_osv", RUN_OSV)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_osv_wrapper_scans_all_repository_lockfiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_run_osv()
    observed: list[dict[str, object]] = []
    version_checks: list[dict[str, object]] = []

    def fake_run_scanner(**kwargs: object) -> int:
        observed.append(kwargs)
        return 0

    monkeypatch.setattr(module, "run_scanner", fake_run_scanner)
    monkeypatch.setattr(
        module, "verify_scanner_version", lambda **kwargs: version_checks.append(kwargs)
    )

    assert module.main(["--required"]) == 0
    assert version_checks == [
        {
            "name": "OSV-Scanner",
            "executable": "osv-scanner",
            "version_args": ("--version",),
            "expected_version": "2.3.8",
            "version_pattern": r"^osv-scanner version:\s+([^\s]+)",
            "required": True,
        }
    ]
    assert len(observed) == 1
    command = observed[0]["command"]
    assert isinstance(command, tuple)
    assert command[:3] == ("osv-scanner", "scan", "source")
    for lockfile in LOCKFILES:
        assert f"--lockfile={lockfile}" in command
    assert observed[0]["token_names"] == ()
    assert observed[0]["required"] is True
    assert observed[0]["cwd"] == ROOT


def test_lockfile_security_floors_cover_current_osv_advisories() -> None:
    package = json.loads(STUDIO_PACKAGE.read_text(encoding="utf-8"))
    overrides = package["pnpm"]["overrides"]

    assert Version(overrides["brace-expansion"]) >= Version("5.0.8")
    assert Version(overrides["postcss"]) >= Version("8.5.18")
    assert Version(overrides["minimatch"]) >= Version("10.2.5")
    assert not any(key.startswith("brace-expansion@") for key in overrides)

    lock = tomllib.loads(UV_LOCK.read_text(encoding="utf-8"))
    pymdown = next(
        package for package in lock["package"] if package["name"] == "pymdown-extensions"
    )
    assert Version(pymdown["version"]) >= Version("11.0.0")


def test_scanner_allowlist_replaces_snyk_with_osv() -> None:
    assert scanner_runner._ALLOWED_EXECUTABLES == frozenset(  # noqa: SLF001
        {"gitleaks", "osv-scanner", "sonar-scanner", "trivy"}
    )


def test_security_workflow_routes_pr_diff_and_full_osv_scans() -> None:
    workflow = SECURITY_WORKFLOW.read_text(encoding="utf-8")

    assert "merge_group:" in workflow
    assert "osv-pr-scan:" in workflow
    assert "osv-full-scan:" in workflow
    assert (
        "google/osv-scanner-action/.github/workflows/osv-scanner-reusable-pr.yml@" + OSV_ACTION_SHA
    ) in workflow
    assert (
        "google/osv-scanner-action/.github/workflows/osv-scanner-reusable.yml@" + OSV_ACTION_SHA
    ) in workflow
    assert "needs.osv-pr-scan.result" in workflow
    assert "needs.osv-full-scan.result" in workflow
    assert "OSV_SCANNER_VERSION" not in workflow
    for lockfile in LOCKFILES:
        assert f"--lockfile={lockfile}" in workflow


def test_local_workflow_uses_osv_without_snyk() -> None:
    taskfile = (ROOT / "Taskfile.yml").read_text(encoding="utf-8")
    pre_commit = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    bootstrap = (ROOT / "scripts" / "bootstrap-dev.sh").read_text(encoding="utf-8")

    assert "security:osv:" in taskfile
    assert "python scripts/run_osv.py --required" in taskfile
    assert "task: security:osv" in taskfile
    assert "security:snyk:" not in taskfile
    assert "run_snyk.py" not in taskfile

    assert "id: osv-maintainer" in pre_commit
    assert "entry: python scripts/run_osv.py" in pre_commit
    assert "stages: [pre-push, manual]" in pre_commit
    assert "snyk-maintainer" not in pre_commit

    assert 'OSV_SCANNER_VERSION="v2.3.8"' in bootstrap
    assert "github.com/google/osv-scanner/v2/cmd/osv-scanner" in bootstrap


def test_active_repository_configuration_has_no_snyk_integration() -> None:
    active_paths = (
        ROOT / ".gitignore",
        ROOT / ".pre-commit-config.yaml",
        ROOT / "Taskfile.yml",
        ROOT / "renovate.json",
        ROOT / "docs" / "developer-security.md",
        ROOT / "docs" / "development.md",
        ROOT / "scripts" / "scanner_runner.py",
    )

    assert not (ROOT / "scripts" / "run_snyk.py").exists()
    forbidden = (
        "security:snyk",
        "run_snyk.py",
        "snyk_token",
        "snyk-maintainer",
        '"snyk"',
    )
    for path in active_paths:
        content = path.read_text(encoding="utf-8").lower()
        for marker in forbidden:
            assert marker not in content, (path.relative_to(ROOT), marker)
