"""Check that every registered MCP tool has a corresponding documentation page.

Compares tool names from ``core/tool_registry._TOOL_SPECS`` against
``docs/tools/*.md`` filenames and reports any gaps.
"""

from __future__ import annotations

from pathlib import Path


def _mcp_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_tool_names() -> set[str]:
    """Extract tool names from _TOOL_SPECS in tool_registry.py."""
    registry_path = _mcp_root() / "src" / "fovux" / "core" / "tool_registry.py"
    content = registry_path.read_text(encoding="utf-8")
    names: set[str] = set()
    in_specs = False
    for line in content.splitlines():
        if "_TOOL_SPECS" in line and "{" in line:
            in_specs = True
            continue
        if in_specs:
            if "}" in line:
                break
            stripped = line.strip()
            if stripped.startswith('"'):
                name = stripped.split('"')[1]
                names.add(name)
    return names


def _load_doc_names() -> set[str]:
    """Scan docs/tools/*.md and return basenames without extension."""
    docs_dir = _mcp_root() / "docs" / "tools"
    if not docs_dir.exists():
        return set()
    return {path.stem for path in docs_dir.glob("*.md")}


def check_tool_docs() -> int:
    """Check completeness and return 0 if all tools have docs, 1 otherwise."""
    tools = _load_tool_names()
    docs = _load_doc_names()
    missing = tools - docs
    extra = docs - tools

    if not missing and not extra:
        print(f"All {len(tools)} tools have documentation pages.")
        return 0

    if missing:
        print(f"MISSING DOCUMENTATION ({len(missing)} tools):")
        for name in sorted(missing):
            print(f"  - {name}")

    if extra:
        print(f"\nEXTRA DOCUMENTATION ({len(extra)} pages with no matching tool):")
        for name in sorted(extra):
            print(f"  - {name}")

    print(f"\nRegistered tools: {len(tools)}")
    print(f"Documentation pages: {len(docs)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(check_tool_docs())
