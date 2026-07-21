"""Contracts for executable packaged-VSIX Studio end-to-end coverage."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
STUDIO = ROOT / "fovux-studio"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_package_scripts_run_installed_vsix_e2e_without_framework_dependencies() -> None:
    package = json.loads(_read(STUDIO / "package.json"))
    scripts = package["scripts"]
    dev_dependencies = package["devDependencies"]

    assert scripts["test:e2e:compile"] == "tsc -p test/e2e/tsconfig.json"
    assert scripts["test:e2e"] == "node test/e2e/run.mjs"
    assert scripts["test:e2e:ci"] == "pnpm run build && pnpm run package && pnpm run test:e2e"
    for forbidden in ("@vscode/test-electron", "mocha", "@types/mocha"):
        assert forbidden not in dev_dependencies


def test_runner_installs_vsix_and_runs_isolated_trust_scenarios() -> None:
    runner = _read(STUDIO / "test" / "e2e" / "run.mjs")

    for phrase in (
        'const VSCODE_VERSION = "1.129.1"',
        "https://update.code.visualstudio.com/",
        "await fetch(VSCODE_DOWNLOAD_URL",
        'const TAR_EXECUTABLE = "/usr/bin/tar"',
        'const SCROT_EXECUTABLE = "/usr/bin/scrot"',
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


def test_extension_host_suite_covers_all_runtime_acceptance_boundaries() -> None:
    suite = _read(STUDIO / "test" / "e2e" / "suite" / "installedExtension.test.ts")

    for phrase in (
        "runInstalledExtensionAssertions",
        "vscode.extensions.getExtension<FovuxStudioApi>(extensionId)",
        "extensionPath",
        "contributedCommands",
        "getDashboardDiagnostics",
        r"webviews\/dashboard\/main\.js",
        "contentSecurityPolicy",
        "HTTP server is offline",
        "rejected this workspace auth token",
        'vscode.commands.executeCommand("fovux.startServer")',
        'vscode.lm.invokeTool("fovux_run_doctor"',
        'url: "/tools/fovux_doctor"',
        "workspaceTrusted",
        "telemetryEnabled",
    ):
        assert phrase in suite


def test_production_webview_exposes_real_ready_and_csp_diagnostics() -> None:
    dashboard = _read(STUDIO / "src" / "webviews" / "dashboard" / "main.tsx")
    command = _read(STUDIO / "src" / "commands" / "openDashboard.ts")
    runtime_api = _read(STUDIO / "src" / "fovux" / "runtimeApi.ts")

    assert 'postToExtension({ type: "webviewReady", view: "dashboard" })' in dashboard
    assert "recordDashboardWebviewReady" in command
    assert "recordDashboardWebviewOpened" in command
    assert "createWebviewDocument" in command
    assert "getDashboardDiagnostics" in runtime_api


def test_ci_runs_xvfb_and_always_uploads_runtime_evidence() -> None:
    workflow_path = ROOT / ".github" / "workflows" / "studio-e2e.yml"
    workflow_text = _read(workflow_path)
    workflow = yaml.safe_load(workflow_text)
    job = workflow["jobs"]["studio-e2e"]

    assert job["name"] == "Studio packaged VSIX E2E"
    assert job["runs-on"] == "ubuntu-24.04"
    assert "xvfb-run -a" in workflow_text
    assert "scrot" in workflow_text
    assert "pnpm run test:e2e:ci" in workflow_text
    assert "if: always()" in workflow_text
    assert "studio-e2e-${{ github.run_id }}" in workflow_text
    assert "fovux-studio/artifacts/studio-e2e" in workflow_text
    assert "fovux-studio/fovuxstudiokit.vsix" in workflow_text


def test_static_checker_requires_dependency_free_executable_e2e_files() -> None:
    checker = _read(ROOT / "scripts" / "check_studio_e2e_smoke.py")

    for phrase in (
        "forbidden_dependencies",
        "installedExtension.test.ts",
        "studio-e2e.yml",
        "--install-extension",
        "getDashboardDiagnostics",
        "fovux_run_doctor",
        "auth-token mismatch",
        "FOVUX_E2E_ARTIFACTS",
    ):
        assert phrase in checker
