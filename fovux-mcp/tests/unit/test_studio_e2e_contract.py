"""Contracts for executable packaged-VSIX Studio end-to-end coverage."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
STUDIO = ROOT / "fovux-studio"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_package_scripts_and_dependencies_run_installed_vsix_e2e() -> None:
    package = json.loads(_read(STUDIO / "package.json"))
    scripts = package["scripts"]
    dev_dependencies = package["devDependencies"]

    assert scripts["test:e2e:compile"] == "tsc -p test/e2e/tsconfig.json"
    assert scripts["test:e2e"] == "node test/e2e/run.mjs"
    assert scripts["test:e2e:ci"] == "pnpm run build && pnpm run package && pnpm run test:e2e"
    assert dev_dependencies["@vscode/test-electron"] == "3.0.0"
    assert dev_dependencies["mocha"] == "11.7.6"
    assert dev_dependencies["@types/mocha"] == "10.0.10"


def test_runner_installs_vsix_and_runs_trusted_and_untrusted_instances() -> None:
    runner = _read(STUDIO / "test" / "e2e" / "run.mjs")

    for phrase in (
        'const VSCODE_VERSION = "1.129.1"',
        "resolveCliArgsFromVSCodeExecutablePath",
        "--install-extension",
        "fovuxstudiokit.vsix",
        "FOVUX_E2E_EXTENSION_PATH",
        'mode: "trusted"',
        'mode: "untrusted"',
        "--disable-workspace-trust",
        "--disable-telemetry",
        "--extensions-dir",
        "--user-data-dir",
    ):
        assert phrase in runner


def test_extension_host_suite_checks_real_packaged_boundary() -> None:
    suite = _read(STUDIO / "test" / "e2e" / "suite" / "installedExtension.test.ts")

    for phrase in (
        "vscode.extensions.getExtension<FovuxStudioApi>(extensionId)",
        "extensionPath",
        "FOVUX_E2E_EXTENSION_PATH",
        "contributedCommands",
        "vscode.commands.executeCommand<DashboardInitialState>",
        "Fovux Dashboard",
        "HTTP server is offline",
        "workspaceTrusted",
        "telemetryEnabled",
        'vscode.commands.executeCommand("fovux.startServer")',
        "fovux_call_tool",
    ):
        assert phrase in suite


def test_ci_runs_xvfb_and_always_uploads_logs_results_screenshots_and_vsix() -> None:
    workflow_path = ROOT / ".github" / "workflows" / "studio-e2e.yml"
    workflow_text = _read(workflow_path)
    workflow = yaml.safe_load(workflow_text)
    jobs = workflow["jobs"]
    job = jobs["studio-e2e"]

    assert job["name"] == "Studio packaged VSIX E2E"
    assert job["runs-on"] == "ubuntu-24.04"
    assert "xvfb-run -a" in workflow_text
    assert "scrot" in workflow_text
    assert "pnpm run test:e2e:ci" in workflow_text
    assert "if: always()" in workflow_text
    assert "studio-e2e-${{ github.run_id }}" in workflow_text
    assert "fovux-studio/artifacts/studio-e2e" in workflow_text
    assert "fovux-studio/fovuxstudiokit.vsix" in workflow_text


def test_static_checker_requires_executable_e2e_files() -> None:
    checker = _read(ROOT / "scripts" / "check_studio_e2e_smoke.py")

    for phrase in (
        "@vscode/test-electron",
        "installedExtension.test.ts",
        "studio-e2e.yml",
        "--install-extension",
        "FOVUX_E2E_ARTIFACTS",
    ):
        assert phrase in checker
