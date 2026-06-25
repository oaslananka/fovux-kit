"""Validate trusted publishing, provenance, and release verification contracts."""

from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    workflows = "\n".join(
        _read(path) for path in (ROOT / ".github" / "workflows").glob("*.yml")
    )
    for phrase in [
        "id-token: write",
        "attest-build-provenance",
        "npm publish --provenance",
        "pypi-production",
        "upload-artifact",
    ]:
        if phrase not in workflows:
            failures.append(f"Release workflows missing {phrase}")
    npm_package = json.loads(_read(ROOT / "fovux-mcp-npm" / "package.json"))
    if npm_package.get("publishConfig", {}).get("provenance") is not True:
        failures.append("npm package publishConfig.provenance must be true")
    for path in [
        "scripts/verify_registry_releases.py",
        "scripts/verify_signatures.sh",
        "docs/release.md",
        "docs/release-process.md",
    ]:
        if not (ROOT / path).exists():
            failures.append(f"Missing release verification file: {path}")
    docs = _read(ROOT / "docs" / "supply-chain-verification.md")
    for phrase in [
        "Trusted Publishing",
        "OIDC",
        "npm publish --provenance",
        "SBOM",
        "SHA256",
        "attestations",
        "verify_registry_releases.py",
    ]:
        if phrase not in docs:
            failures.append(f"Supply-chain docs missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Supply-chain publishing checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
