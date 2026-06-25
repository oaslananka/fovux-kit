"""Regenerate README tool inventory tables from the central registry."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MCP_ROOT = ROOT / "fovux-mcp"
SRC = MCP_ROOT / "src"
START = "<!-- fovux-tools:start -->"
END = "<!-- fovux-tools:end -->"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fovux.core.tool_registry import list_tool_names  # noqa: E402


def _description_for_tool(name: str) -> str:
    """Return the first docstring line for a registered tool."""
    from fovux.core.tool_registry import resolve_tool

    doc = (resolve_tool(name).__doc__ or "").strip().splitlines()
    if not doc:
        raise SystemExit(f"Tool {name} is missing a docstring description")
    return doc[0].strip()


def render_table() -> str:
    """Render the Markdown table for all registered tools."""
    rows = ["| Tool | Purpose |", "|---|---|"]
    for name in list_tool_names():
        rows.append(f"| `{name}` | {_description_for_tool(name)} |")
    return "\n".join(rows)


def replace_block(path: Path, table: str) -> None:
    """Replace the generated table block in a Markdown document."""
    text = path.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit(f"{path} is missing {START}/{END} markers")
    before, rest = text.split(START, maxsplit=1)
    _, after = rest.split(END, maxsplit=1)
    path.write_text(f"{before}{START}\n{table}\n{END}{after}", encoding="utf-8")


def main() -> None:
    """Regenerate tool tables in the root and MCP READMEs."""
    table = render_table()
    replace_block(ROOT / "README.md", table)
    replace_block(MCP_ROOT / "README.md", table)


if __name__ == "__main__":
    main()
