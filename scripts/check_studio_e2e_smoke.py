"""Validate executable packaged-VSIX Studio end-to-end coverage contracts."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDIO = ROOT / "fovux-studio"


def _read(path: Path, failures: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        failures.append(f"cannot read {path.relative_to(ROOT)}: {exc}")
        return ""


def _require(
    text: str, phrases: tuple[str, ...], *, label: str, failures: list[str]
) -> None:
    for phrase in phrases:
        if phrase not in text:
            failures.append(f"{label} missing {phrase}")


def main() -> int:
    """Validate the packaged VSIX E2E implementation contract."""
    failures: list[str] = []
    package_text = _read(STUDIO / "package.json", failures)
    package = json.loads(package_text) if package_text else {}
    scripts = package.get("scripts", {})
    dependencies = package.get("devDependencies", {})

    expected_scripts = {
        "test:e2e:compile": "tsc -p test/e2e/tsconfig.json",
        "pretest:e2e": "pnpm run test:e2e:compile",
        "test:e2e": "node test/e2e/run.mjs",
        "test:e2e:ci": "pnpm run build && pnpm run package && pnpm run test:e2e",
    }
    for name, expected in expected_scripts.items():
        if scripts.get(name) != expected:
            failures.append(f"package.json script {name} must be {expected!r}")

    forbidden_dependencies = ("@vscode/test-electron", "mocha", "@types/mocha")
    for name in forbidden_dependencies:
        if name in dependencies:
            failures.append(
                f"package.json must not add E2E framework dependency {name}"
            )
    if ".vsix" not in scripts.get("package", ""):
        failures.append("package script must create a VSIX")

    runner = _read(STUDIO / "test" / "e2e" / "run.mjs", failures)
    _require(
        runner,
        (
            'const VSCODE_VERSION = "1.129.1"',
            "https://update.code.visualstudio.com/",
            "await fetch(VSCODE_DOWNLOAD_URL",
            'join(installationRoot, "VSCode-linux-x64", "bin", "code")',
            'const TAR_EXECUTABLE = "/usr/bin/tar"',
            'const SCROT_EXECUTABLE = "/usr/bin/scrot"',
            "--install-extension",
            "fovuxstudiokit.vsix",
            'mode: "trusted"',
            'mode: "untrusted"',
            "--disable-workspace-trust",
            "--extensions-dir",
            "--user-data-dir",
            "--disable-telemetry",
            "FOVUX_E2E_ARTIFACTS",
            "FOVUX_E2E_EXTENSION_PATH",
            "extension-host.log",
        ),
        label="Studio E2E runner",
        failures=failures,
    )

    suite = _read(
        STUDIO / "test" / "e2e" / "suite" / "installedExtensionAssertions.ts", failures
    )
    _require(
        suite,
        (
            "runInstalledExtensionAssertions",
            "vscode.extensions.getExtension<FovuxStudioApi>(extensionId)",
            "extension.extensionPath",
            "contributedCommands",
            "getDashboardDiagnostics",
            "contentSecurityPolicy",
            "HTTP server is offline",
            "auth-token mismatch",
            "rejected this workspace auth token",
            'vscode.commands.executeCommand("fovux.startServer")',
            'vscode.lm.invokeTool("fovux_run_doctor"',
            'url: "/tools/fovux_doctor"',
            "workspaceTrusted",
            "telemetryEnabled",
        ),
        label="installed VSIX suite",
        failures=failures,
    )

    harness = _read(STUDIO / "test" / "e2e" / "suite" / "index.ts", failures)
    _require(
        harness,
        ("runInstalledExtensionAssertions", "result.json", "scrot", "failure.png"),
        label="E2E evidence harness",
        failures=failures,
    )

    tsconfig = _read(STUDIO / "test" / "e2e" / "tsconfig.json", failures)
    if '"mocha"' in tsconfig:
        failures.append("Studio E2E tsconfig must not load Mocha types")

    dashboard = _read(STUDIO / "src" / "webviews" / "dashboard" / "main.tsx", failures)
    _require(
        dashboard,
        ('postToExtension({ type: "webviewReady", view: "dashboard" })',),
        label="dashboard bundle handshake",
        failures=failures,
    )
    command = _read(STUDIO / "src" / "commands" / "openDashboard.ts", failures)
    _require(
        command,
        (
            "recordDashboardWebviewOpened",
            "recordDashboardWebviewReady",
            "createWebviewDocument",
        ),
        label="dashboard extension handshake",
        failures=failures,
    )
    runtime_api = _read(STUDIO / "src" / "fovux" / "runtimeApi.ts", failures)
    _require(
        runtime_api,
        ("getDashboardDiagnostics", "getDashboardWebviewDiagnostics"),
        label="Studio runtime diagnostics API",
        failures=failures,
    )

    workflow = _read(ROOT / ".github" / "workflows" / "studio-e2e.yml", failures)
    _require(
        workflow,
        (
            "Studio packaged VSIX E2E",
            "ubuntu-24.04",
            "xvfb-run -a",
            "scrot",
            "pnpm run test:e2e:ci",
            "if: failure()",
            "studio-e2e-${{ github.run_id }}",
            "fovux-studio/artifacts/studio-e2e",
            "fovux-studio/fovuxstudiokit.vsix",
            "retention-days: 7",
        ),
        label="Studio E2E workflow",
        failures=failures,
    )

    docs = _read(ROOT / "docs" / "studio-e2e-smoke-contract.md", failures)
    _require(
        docs,
        (
            "installed VSIX",
            "Workspace Trust",
            "backend-offline",
            "auth-token mismatch",
            "webviewReady",
            "Content Security Policy",
            "vscode.lm.invokeTool",
            "No telemetry",
            "dependency-free",
            "artifacts/studio-e2e",
            "failure screenshot",
        ),
        label="Studio E2E documentation",
        failures=failures,
    )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Studio executable E2E checks passed: dependency-free VS Code download, packaged VSIX "
        "installation, trusted/untrusted activation, backend-offline and auth-token mismatch "
        "handling, CSP-protected webview handshake, Language Model tool invocation, no-telemetry "
        "metadata, and failure evidence are aligned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
