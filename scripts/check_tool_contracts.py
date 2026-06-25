"""Verify MCP tool schema snapshots and cross-surface tool contracts."""

from __future__ import annotations
import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MCP_ROOT = ROOT / "fovux-mcp"
STUDIO_ROOT = ROOT / "fovux-studio"
SRC = MCP_ROOT / "src"
SNAPSHOT = MCP_ROOT / "tests" / "snapshots" / "mcp_tool_schemas.json"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
from fastmcp import Client  # noqa: E402
from fovux.core.tool_registry import list_tool_names, resolve_tool  # noqa: E402
from fovux.http.tool_proxy import HTTP_TOOL_POLICIES  # noqa: E402
from fovux.server import mcp  # noqa: E402


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def stable(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def docs_path(name: str) -> Path:
    return MCP_ROOT / "docs" / "tools" / f"{name}.md"


def all_tests_text() -> str:
    return "\n".join(
        p.read_text(encoding="utf-8", errors="ignore")
        for p in (MCP_ROOT / "tests").rglob("test_*.py")
    )


def studio_mappings() -> tuple[list[str], list[str]]:
    content = read(STUDIO_ROOT / "src" / "fovux" / "tools" / "definitions.ts")
    blocks = re.findall(r'\{\n\s+name:\s+"fovux_[\s\S]*?\n\s+\},', content)
    mapped = re.findall(r'mcpToolName:\s*"([^"]+)"', content)
    studio_only = [
        b for b in blocks if "mcpToolName:" not in b and "studioOnlyReason:" in b
    ]
    missing = []
    for block in blocks:
        if "mcpToolName:" not in block and "studioOnlyReason:" not in block:
            m = re.search(r'name:\s*"([^"]+)"', block)
            missing.append(m.group(1) if m else "<unknown>")
    if missing:
        raise AssertionError(
            "Studio LM tools without mcpToolName or studioOnlyReason: "
            + ", ".join(sorted(missing))
        )
    return mapped, studio_only


async def records() -> list[dict[str, Any]]:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    by_name = {tool.name: tool for tool in tools}
    out = []
    for name in list_tool_names():
        tool = by_name[name]
        policy = HTTP_TOOL_POLICIES[name]
        fn = resolve_tool(name)
        out.append(
            {
                "name": name,
                "owner": "oaslananka",
                "component": "fovux-mcp",
                "callable": f"{fn.__module__}:{fn.__name__}",
                "docs_page": docs_path(name).relative_to(ROOT).as_posix(),
                "description": tool.description,
                "title": tool.title,
                "inputSchema": tool.inputSchema,
                "outputSchema": tool.outputSchema,
                "annotations": tool.annotations.model_dump(mode="json")
                if tool.annotations is not None
                else None,
                "http_policy": {
                    "category": policy.category,
                    "timeout_seconds": policy.timeout_seconds,
                    "concurrency_limit": policy.concurrency_limit,
                    "requires_confirmation": policy.requires_confirmation,
                    "enabled": policy.enabled,
                    "required_scope": policy.required_scope.value,
                },
            }
        )
    return out


async def build_snapshot() -> dict[str, Any]:
    mapped, studio_only = studio_mappings()
    return {
        "schema_version": 1,
        "source": "fovux.core.tool_registry + FastMCP list_tools + HTTP_TOOL_POLICIES",
        "tool_count": len(list_tool_names()),
        "studio_lm_tool_count": len(mapped) + len(studio_only),
        "studio_mcp_mappings": sorted(mapped),
        "studio_only_tools": studio_only,
        "tools": await records(),
    }


def readme_tools(path: Path) -> list[str]:
    m = re.search(
        r"<!-- fovux-tools:start -->\n(?P<table>.*?)\n<!-- fovux-tools:end -->",
        read(path),
        flags=re.S,
    )
    if not m:
        raise AssertionError(f"{path} is missing generated tool table markers")
    return re.findall(r"\| `([a-z0-9_]+)`", m.group("table"))


def validate(snapshot: dict[str, Any]) -> list[str]:
    failures = []
    names = list_tool_names()
    record_names = [r["name"] for r in snapshot["tools"]]
    if record_names != names:
        failures.append(f"Snapshot tool order mismatch: {record_names} != {names}")
    policy_names = sorted(HTTP_TOOL_POLICIES)
    if policy_names != names:
        failures.append(
            f"HTTP_TOOL_POLICIES drift: missing={sorted(set(names) - set(policy_names))} extra={sorted(set(policy_names) - set(names))}"
        )
    test_text = all_tests_text()
    for record in snapshot["tools"]:
        name = record["name"]
        if not docs_path(name).exists():
            failures.append(f"Missing docs page for tool: {name}")
        if name not in test_text:
            failures.append(f"Missing test reference for tool: {name}")
        if record["owner"] != "oaslananka" or record["component"] != "fovux-mcp":
            failures.append(f"Missing owner/component metadata for tool: {name}")
        if not record["description"]:
            failures.append(f"Missing description for tool: {name}")
        if record["inputSchema"].get("type") != "object":
            failures.append(f"Input schema for {name} must be object")
        if (
            record["outputSchema"] is not None
            and record["outputSchema"].get("type") != "object"
        ):
            failures.append(f"Output schema for {name} must be object")
    mapped, _ = studio_mappings()
    unknown = sorted(set(mapped) - set(names))
    if unknown:
        failures.append(f"Studio LM tools map to unknown MCP tools: {unknown}")
    found = readme_tools(MCP_ROOT / "README.md")
    if found != names:
        failures.append("fovux-mcp/README.md tool table drift")
    root_readme = read(ROOT / "README.md")
    if (
        "fovux-mcp/README.md" not in root_readme
        or "generated complete tool list" not in root_readme
    ):
        failures.append("Root README must link to the generated MCP tool table")
    return failures


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    snapshot = await build_snapshot()
    failures = validate(snapshot)
    if args.update:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(stable(snapshot), encoding="utf-8")
        print(f"Updated {SNAPSHOT.relative_to(ROOT)}")
        return 0 if not failures else 1
    if not SNAPSHOT.exists():
        failures.append(f"Missing snapshot: {SNAPSHOT.relative_to(ROOT)}")
    else:
        if json.loads(SNAPSHOT.read_text(encoding="utf-8")) != snapshot:
            failures.append(
                "MCP tool schema snapshot drift. Run: python scripts/check_tool_contracts.py --update"
            )
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Tool contract checks passed: schema snapshot, docs, tests, HTTP policy metadata, Studio mappings, and README tables are synchronized."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
