"""Validate Studio VSIX release evidence, size gate, and rollback playbook."""

from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    workflow = _read(ROOT / ".github" / "workflows" / "publish-production.yml")
    for phrase in [
        "Package VSIX",
        "Upload VSIX artifact",
        "sha256sum",
        "attest-build-provenance",
        "registry-verification",
        "--max-size-bytes",
    ]:
        if phrase not in workflow:
            failures.append(f"publish workflow missing {phrase}")
    packager = _read(ROOT / "scripts" / "package_vscode_extension.mjs")
    for phrase in [
        ".vscodeignore",
        "--max-size-bytes",
        "VSIX_PACKAGE_TOO_LARGE",
        "extension.vsixmanifest",
    ]:
        if phrase not in packager:
            failures.append(f"packager missing {phrase}")
    package = json.loads(_read(ROOT / "fovux-studio" / "package.json"))
    scripts = package.get("scripts", {})
    for name in ["package", "test:e2e"]:
        if name not in scripts:
            failures.append(f"studio package missing script {name}")
    docs = _read(ROOT / "docs" / "studio-release-playbook.md")
    for phrase in [
        "VSIX",
        "Open VSX",
        "Marketplace",
        "SHA256",
        "SBOM",
        "rollback",
        "unpublish",
        "Package-size gate",
    ]:
        if phrase not in docs:
            failures.append(f"studio release docs missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Studio release evidence checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
