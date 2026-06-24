"""Check that every registered MCP tool has a corresponding documentation page.

Compares tool names from ``core/tool_registry._TOOL_SPECS`` against
``docs/tools/*.md`` filenames and reports any gaps.
"""

from __future__ import annotations

from pathlib import Path

import yaml


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
            if stripped.startswith('"') and '":' in stripped:
                name = stripped.split('"')[1]
                names.add(name)
    return names


def _load_doc_names() -> set[str]:
    """Scan docs/tools/*.md and return basenames without extension."""
    docs_dir = _mcp_root() / "docs" / "tools"
    if not docs_dir.exists():
        return set()
    return {path.stem for path in docs_dir.glob("*.md")}


def _iter_nav_paths(node: object) -> set[str]:
    """Return Markdown paths referenced by mkdocs.yml nav entries."""
    paths: set[str] = set()
    if isinstance(node, str) and node.endswith(".md"):
        paths.add(node)
    elif isinstance(node, list):
        for item in node:
            paths.update(_iter_nav_paths(item))
    elif isinstance(node, dict):
        for value in node.values():
            paths.update(_iter_nav_paths(value))
    return paths


def _load_nav_doc_paths() -> set[str]:
    """Parse mkdocs.yml and return docs-relative Markdown paths in nav."""
    config_path = _mcp_root() / "mkdocs.yml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    nav = config.get("nav", []) if isinstance(config, dict) else []
    return _iter_nav_paths(nav)


def check_tool_docs() -> int:
    """Check tool documentation and MkDocs nav coverage."""
    tools = _load_tool_names()
    docs = _load_doc_names()
    missing = tools - docs
    extra = docs - tools

    nav_paths = _load_nav_doc_paths()
    expected_tool_paths = {f"tools/{name}.md" for name in docs}
    missing_from_nav = expected_tool_paths - nav_paths

    if not missing and not extra and not missing_from_nav:
        print(f"All {len(tools)} tools have documentation pages and MkDocs nav entries.")
        return 0

    if missing:
        print(f"MISSING DOCUMENTATION ({len(missing)} tools):")
        for name in sorted(missing):
            print(f"  - {name}")

    if extra:
        print(f"\nEXTRA DOCUMENTATION ({len(extra)} pages with no matching tool):")
        for name in sorted(extra):
            print(f"  - {name}")

    if missing_from_nav:
        print(f"\nMISSING MKDOCS NAV ENTRIES ({len(missing_from_nav)} tool pages):")
        for path in sorted(missing_from_nav):
            print(f"  - {path}")

    print(f"\nRegistered tools: {len(tools)}")
    print(f"Documentation pages: {len(docs)}")
    print(f"Tool nav entries: {len(expected_tool_paths - missing_from_nav)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(check_tool_docs())
