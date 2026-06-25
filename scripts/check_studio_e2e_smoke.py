"""Validate Studio e2e smoke-test and release evidence contracts."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    package = json.loads(_read(ROOT / "fovux-studio" / "package.json"))
    scripts = package.get("scripts", {})
    for name in ["test:e2e", "package", "test", "typecheck"]:
        if name not in scripts:
            failures.append(f"package.json missing script {name}")
    if "vscode-test" not in scripts.get("test:e2e", ""):
        failures.append("test:e2e must use vscode-test")
    if ".vsix" not in scripts.get("package", ""):
        failures.append("package script must create a VSIX")
    extension_tests = _read(
        ROOT / "fovux-studio" / "test" / "suite" / "extension.test.ts"
    )
    for phrase in [
        "registers all user-facing commands",
        "dashboard webview",
        "local resource roots",
        "untrustedWorkspaces",
        "HTTP server is offline",
    ]:
        if phrase not in extension_tests:
            failures.append(f"extension smoke tests missing {phrase}")
    lm_tests = _read(
        ROOT / "fovux-studio" / "test" / "suite" / "languageModelTools.test.ts"
    )
    for phrase in [
        "registers all granular tools",
        "prepareInvocation",
        "fovux_call_tool",
    ]:
        if phrase not in lm_tests:
            failures.append(f"LM tool smoke tests missing {phrase}")
    release = _read(ROOT / ".github" / "workflows" / "publish-production.yml")
    for phrase in [
        "Package VSIX",
        "Upload VSIX artifact",
        "--vsix",
        "upload-artifact",
        "registry-verification",
    ]:
        if phrase not in release:
            failures.append(f"release e2e evidence missing {phrase}")
    docs = _read(ROOT / "docs" / "studio-e2e-smoke-contract.md")
    for phrase in [
        "Built VSIX",
        "test:e2e",
        "Workspace Trust",
        "backend-offline",
        "No telemetry",
    ]:
        if phrase not in docs:
            failures.append(f"e2e docs missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Studio e2e smoke checks passed: package scripts, activation/webview/offline/LM tests, release artifacts, and docs are aligned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
