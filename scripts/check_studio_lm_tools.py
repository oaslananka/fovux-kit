"""Validate VS Code Language Model Tool metadata and backend mapping."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP_ROOT = ROOT / "fovux-mcp"
STUDIO_ROOT = ROOT / "fovux-studio"
SRC = MCP_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fovux.core.tool_registry import list_tool_names  # noqa: E402

NAME_RE = re.compile(r"^fovux_[a-z]+_[a-z0-9_]+$")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _definition_blocks() -> list[str]:
    content = _read(STUDIO_ROOT / "src" / "fovux" / "tools" / "definitions.ts")
    return re.findall(r"\{\n\s+name:\s+\"fovux_[\s\S]*?\n\s+\},", content)


def _field(block: str, name: str) -> str | None:
    match = re.search(rf'{name}:\s*"([^"]+)"', block)
    return match.group(1) if match else None


def main() -> int:
    failures: list[str] = []
    package = json.loads(_read(STUDIO_ROOT / "package.json"))
    package_tools = package["contributes"]["languageModelTools"]
    package_names = {tool["name"] for tool in package_tools}
    blocks = _definition_blocks()
    definition_names = {_field(block, "name") for block in blocks}
    definition_names.discard(None)
    if package_names != definition_names | {"fovux_call_tool"}:
        failures.append(
            "package.json LM tool names do not match granular definitions plus dispatcher"
        )

    backend = set(list_tool_names())
    mapped_backend: set[str] = set()
    for tool in package_tools:
        name = str(tool.get("name", ""))
        if not NAME_RE.fullmatch(name):
            failures.append(f"LM tool name must follow fovux_{{verb}}_{{noun}}: {name}")
        for field in [
            "displayName",
            "modelDescription",
            "userDescription",
            "inputSchema",
        ]:
            if field not in tool:
                failures.append(f"{name} missing package.json field {field}")
        if len(str(tool.get("modelDescription", ""))) < 80:
            failures.append(f"{name} modelDescription is too short for LLM routing")
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            failures.append(f"{name} inputSchema must be an object schema")

    for block in blocks:
        name = _field(block, "name") or "<unknown>"
        mcp = _field(block, "mcpToolName")
        for field in [
            "toolReferenceName",
            "displayName",
            "modelDescription",
            "userDescription",
        ]:
            if _field(block, field) is None:
                failures.append(f"{name} missing definitions.ts field {field}")
        if mcp is None:
            if "studioOnlyReason:" not in block:
                failures.append(f"{name} missing mcpToolName or studioOnlyReason")
        elif mcp not in backend:
            failures.append(f"{name} maps to unknown backend tool {mcp}")
        else:
            mapped_backend.add(mcp)

    docs = _read(ROOT / "docs" / "studio-language-model-tools.md")
    for phrase in [
        "fovux_{verb}_{noun}",
        "userDescription",
        "modelDescription",
        "prepareInvocation",
        "Backend tools not directly exposed",
        "Active-learning queue tools",
        "Runtime-heavy live streams",
    ]:
        if phrase not in docs:
            failures.append(f"Studio LM tools doc missing phrase: {phrase}")

    if not (backend - mapped_backend):
        failures.append(
            "Expected a documented curated subset; all backend tools are exposed unexpectedly"
        )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Studio LM tool checks passed: names, descriptions, schemas, mappings, and docs are aligned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
