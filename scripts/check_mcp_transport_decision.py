"""Fail-fast checks for the MCP stdio vs Studio local API decision."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP_ROOT = ROOT / "fovux-mcp"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    """Verify that the Studio local API is not advertised as Streamable HTTP MCP."""
    failures: list[str] = []
    adr = _read(MCP_ROOT / "docs" / "adr" / "0004-stdio-vs-http-transport.md")
    conformance = _read(MCP_ROOT / "docs" / "mcp-conformance.md")
    architecture = _read(ROOT / "docs" / "architecture.md")
    integrations = _read(MCP_ROOT / "docs" / "integrations.md")
    cli = _read(MCP_ROOT / "src" / "fovux" / "cli.py")
    app = _read(MCP_ROOT / "src" / "fovux" / "http" / "app.py")
    routes = "\n".join(
        _read(path) for path in (MCP_ROOT / "src" / "fovux" / "http").glob("*.py")
    )

    for phrase in [
        "Accepted on 2026-06-24",
        "Keep `fovux-mcp` stdio as the supported MCP transport",
        "Fovux Studio local API",
        "Do not expose an official `/mcp` Streamable HTTP endpoint",
        "Backwards compatibility plan",
    ]:
        _expect(phrase in adr, f"ADR 0004 missing decision phrase: {phrase}", failures)

    for phrase in [
        "MCP 2025-11-25 Conformance",
        "Streamable HTTP transport      | Not exposed",
        "all 47 tools",
        "Studio local API auth",
        "Streamable HTTP Implementation Requirements",
    ]:
        _expect(
            phrase in conformance,
            f"MCP conformance doc missing phrase: {phrase}",
            failures,
        )

    _expect(
        "Studio local HTTP/SSE API" in architecture
        and "not documented as a standards-compliant MCP Streamable HTTP endpoint"
        in architecture,
        "Architecture doc must distinguish the Studio local API from MCP Streamable HTTP.",
        failures,
    )
    _expect(
        "Fovux Studio local API/custom REST+SSE bridge" in integrations,
        "Integrations doc must name serve --http as the Studio local API/custom bridge.",
        failures,
    )
    _expect(
        "Enable the Fovux Studio local API/custom REST+SSE bridge" in cli
        and "Studio local API" in cli,
        "CLI help and doctor labels must use Studio local API terminology.",
        failures,
    )
    _expect(
        "This is not an MCP Streamable HTTP" in app,
        "HTTP app module docstring must explicitly say it is not MCP Streamable HTTP.",
        failures,
    )
    _expect(
        not re.search(r'@(router|app)\.(get|post|delete)\(["\']/mcp["\']', routes),
        "A /mcp route exists without being covered by this decision gate.",
        failures,
    )
    for legacy_cli_phrase in [
        "Enable HTTP transport.",
        "Start the MCP server (stdio by default, or HTTP with --http).",
        "HTTP transport",
    ]:
        _expect(
            legacy_cli_phrase not in cli,
            f"Legacy generic transport wording remains in CLI: {legacy_cli_phrase}",
            failures,
        )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1

    print(
        "MCP transport decision checks passed: stdio is MCP, serve --http is Studio local API, /mcp is not exposed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
