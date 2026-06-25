"""Validate MCP Apps product strategy decision."""

from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    adr = _read(ROOT / "docs" / "adr" / "0002-mcp-apps-ui-strategy.md")
    for phrase in [
        "MCP Apps",
        "Defer",
        "Fovux Studio",
        "read-only",
        "Workspace Trust",
        "2026-12-31",
        "Next experiment",
    ]:
        if phrase not in adr:
            failures.append(f"MCP Apps ADR missing {phrase}")
    for path in [
        "docs/adr/0001-api-stability-and-plugins.md",
        "docs/studio-e2e-smoke-contract.md",
        "docs/studio-release-playbook.md",
        "docs/threat-model.md",
    ]:
        if not (ROOT / path).exists():
            failures.append(f"Missing related strategy input: {path}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("MCP Apps strategy checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
