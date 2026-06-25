"""Validate API stability, plugin, and 2.0 migration planning docs."""

from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    adr = _read(ROOT / "docs" / "adr" / "0001-api-stability-and-plugins.md")
    for phrase in [
        "CLI",
        "MCP",
        "Studio",
        "HTTP",
        "Config",
        "Semver",
        "Plugin capability model",
        "migration checklist",
    ]:
        if phrase.lower() not in adr.lower():
            failures.append(f"ADR missing {phrase}")
    for phrase in [
        "tool schema snapshots",
        "breaking",
        "policy scopes",
        "human confirmation",
        "no-telemetry",
        "Workspace Trust",
    ]:
        if phrase.lower() not in adr.lower():
            failures.append(f"ADR missing {phrase}")
    for path in [
        "docs/api-stability.md",
        "docs/architecture.md",
        "docs/mcp-client-compatibility.md",
    ]:
        if not (ROOT / path).exists():
            failures.append(f"Missing related architecture doc: {path}")
    snapshot = ROOT / "fovux-mcp" / "tests" / "snapshots" / "mcp_tool_schemas.json"
    if not snapshot.exists():
        failures.append("Missing MCP tool schema snapshot gate")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("API stability plan checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
