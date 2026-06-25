"""Validate MCP client compatibility docs and smoke-test coverage."""

from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "mcp-client-compatibility.md"
RUNTIME = ROOT / "docs" / "runtime-compatibility.md"
CONTRACT = ROOT / "fovux-mcp" / "tests" / "contract" / "test_mcp_protocol.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    doc = _read(DOC)
    required = [
        "Client / host",
        "OS",
        "Transport",
        "Install method",
        "Smoke command",
        "Status",
        "Known limitations",
        "Raw JSON-RPC stdio",
        "Claude Desktop",
        "VS Code MCP host",
        "Generic hosted MCP client",
        "Manual GUI checklist",
        "all 47 MCP tools",
        "model_list",
    ]
    required.append("unknown " + "tool")
    for phrase in required:
        if phrase not in doc:
            failures.append(f"Compatibility matrix missing phrase: {phrase}")
    runtime = _read(RUNTIME)
    if "mcp-client-compatibility.md" not in runtime:
        failures.append(
            "Runtime compatibility docs must link MCP client compatibility results"
        )
    contract = _read(CONTRACT)
    for phrase in [
        "test_raw_stdio_jsonrpc_initialize_list_call_error_and_cancel",
        "tools/list",
        "tools/call",
        "notifications/cancelled",
        "fovux/unknown_method",
    ]:
        if phrase not in contract:
            failures.append(f"Raw JSON-RPC contract coverage missing: {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "MCP client compatibility checks passed: matrix, manual checklist, runtime link, and raw JSON-RPC smoke coverage are present."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
