"""Verify MCP implementation schemas, runtime manifest, docs, and cross-surface contracts."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent.parent
MCP_ROOT = ROOT / "fovux-mcp"
STUDIO_ROOT = ROOT / "fovux-studio"
SRC = MCP_ROOT / "src"
SNAPSHOT = MCP_ROOT / "tests" / "snapshots" / "mcp_tool_schemas.json"
RUNTIME_MANIFEST = SRC / "fovux" / "tool_manifest.json"
STUDIO_OVERRIDES = STUDIO_ROOT / "src" / "fovux" / "tools" / "overrides.json"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastmcp import Client  # noqa: E402
from fastmcp.tools import FunctionTool  # noqa: E402

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
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (MCP_ROOT / "tests").rglob("test_*.py")
    )


def studio_mappings() -> tuple[list[str], list[str]]:
    """Return the explicit curated backend subset from Studio UX overrides."""
    overrides = json.loads(read(STUDIO_OVERRIDES))
    if not isinstance(overrides, dict) or overrides.get("schemaVersion") != 1:
        raise AssertionError("Studio LM overrides must be a schemaVersion 1 object")
    tools = overrides.get("tools")
    if not isinstance(tools, dict) or not tools:
        raise AssertionError(
            "Studio LM overrides must contain a non-empty tools object"
        )
    mapped = list(tools)
    if any(not isinstance(name, str) or not name for name in mapped):
        raise AssertionError("Studio LM override keys must be backend tool names")
    return mapped, []


def implementation_records() -> list[dict[str, Any]]:
    """Build canonical records directly from implementation signatures and metadata."""
    records: list[dict[str, Any]] = []
    for name in list_tool_names():
        fn = resolve_tool(name)
        tool = FunctionTool.from_function(fn)
        policy = HTTP_TOOL_POLICIES[name]
        records.append(
            {
                "name": name,
                "owner": "oaslananka",
                "component": "fovux-mcp",
                "callable": f"{fn.__module__}:{fn.__name__}",
                "docs_page": docs_path(name).relative_to(ROOT).as_posix(),
                "description": tool.description,
                "title": tool.title,
                "inputSchema": tool.parameters,
                "outputSchema": tool.output_schema,
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
    return records


def build_snapshot() -> dict[str, Any]:
    mapped, studio_only = studio_mappings()
    return {
        "schema_version": 1,
        "source": "fovux.core.tool_registry + FunctionTool schemas + HTTP_TOOL_POLICIES",
        "tool_count": len(list_tool_names()),
        "studio_lm_tool_count": len(mapped) + len(studio_only),
        "studio_mcp_mappings": sorted(mapped),
        "studio_only_tools": studio_only,
        "tools": implementation_records(),
    }


def build_runtime_manifest(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Project the canonical snapshot into the minimal packaged runtime manifest."""
    manifest_records = []
    for record in cast(list[dict[str, Any]], snapshot["tools"]):
        manifest_records.append(
            {
                "name": record["name"],
                "callable": record["callable"],
                "description": record["description"],
                "title": record["title"],
                "inputSchema": record["inputSchema"],
                "outputSchema": record["outputSchema"],
                "annotations": record["annotations"],
            }
        )
    return {
        "schema_version": 1,
        "source": "fovux-mcp/tests/snapshots/mcp_tool_schemas.json",
        "tool_count": snapshot["tool_count"],
        "tools": manifest_records,
    }


def readme_tools(path: Path) -> list[str]:
    match = re.search(
        r"<!-- fovux-tools:start -->\n(?P<table>.*?)\n<!-- fovux-tools:end -->",
        read(path),
        flags=re.S,
    )
    if not match:
        raise AssertionError(f"{path} is missing generated tool table markers")
    return re.findall(r"\| `([a-z0-9_]+)`", match.group("table"))


def _validate_registry_alignment(
    names: list[str],
    records: list[dict[str, Any]],
) -> list[str]:
    """Validate snapshot ordering and HTTP policy membership."""
    failures: list[str] = []
    record_names = [str(record["name"]) for record in records]
    if record_names != names:
        failures.append(f"Snapshot tool order mismatch: {record_names} != {names}")
    policy_names = sorted(HTTP_TOOL_POLICIES)
    if policy_names != names:
        failures.append(
            "HTTP_TOOL_POLICIES drift: "
            f"missing={sorted(set(names) - set(policy_names))} "
            f"extra={sorted(set(policy_names) - set(names))}"
        )
    return failures


def _validate_record(record: dict[str, Any], test_text: str) -> list[str]:
    """Validate documentation, ownership, and schemas for one tool record."""
    failures: list[str] = []
    name = str(record["name"])
    if not docs_path(name).exists():
        failures.append(f"Missing docs page for tool: {name}")
    if name not in test_text:
        failures.append(f"Missing test reference for tool: {name}")
    if record["owner"] != "oaslananka" or record["component"] != "fovux-mcp":
        failures.append(f"Missing owner/component metadata for tool: {name}")
    if not record["description"]:
        failures.append(f"Missing description for tool: {name}")
    input_schema = record["inputSchema"]
    output_schema = record["outputSchema"]
    if not isinstance(input_schema, dict) or input_schema.get("type") != "object":
        failures.append(f"Input schema for {name} must be object")
    if output_schema is not None and (
        not isinstance(output_schema, dict) or output_schema.get("type") != "object"
    ):
        failures.append(f"Output schema for {name} must be object")
    return failures


def _validate_cross_surface_docs(names: list[str]) -> list[str]:
    """Validate Studio mappings and generated README references."""
    failures: list[str] = []
    mapped, _ = studio_mappings()
    unknown = sorted(set(mapped) - set(names))
    if unknown:
        failures.append(f"Studio LM tools map to unknown MCP tools: {unknown}")
    if readme_tools(MCP_ROOT / "README.md") != names:
        failures.append("fovux-mcp/README.md tool table drift")
    root_readme = read(ROOT / "README.md")
    if (
        "fovux-mcp/README.md" not in root_readme
        or "generated complete tool list" not in root_readme
    ):
        failures.append("Root README must link to the generated MCP tool table")
    return failures


def validate_static(snapshot: dict[str, Any]) -> list[str]:
    """Validate static registry, per-tool, and cross-surface contracts."""
    names = list_tool_names()
    records = cast(list[dict[str, Any]], snapshot["tools"])
    failures = _validate_registry_alignment(names, records)
    test_text = all_tests_text()
    for record in records:
        failures.extend(_validate_record(record, test_text))
    failures.extend(_validate_cross_surface_docs(names))
    return failures


async def validate_runtime(snapshot: dict[str, Any]) -> list[str]:
    """Ensure the lazy runtime surface exactly matches implementation-derived schemas."""
    failures: list[str] = []
    expected = {
        str(record["name"]): record
        for record in cast(list[dict[str, Any]], snapshot["tools"])
    }
    async with Client(mcp) as client:
        runtime_tools = await client.list_tools()
    runtime_names = sorted(tool.name for tool in runtime_tools)
    if runtime_names != sorted(expected):
        failures.append(
            f"Runtime tool names drifted: {runtime_names} != {sorted(expected)}"
        )
        return failures
    for tool in runtime_tools:
        record = expected[tool.name]
        runtime_annotations = (
            tool.annotations.model_dump(mode="json")
            if tool.annotations is not None
            else None
        )
        comparisons = {
            "description": (tool.description, record["description"]),
            "title": (tool.title, record["title"]),
            "inputSchema": (tool.inputSchema, record["inputSchema"]),
            "outputSchema": (tool.outputSchema, record["outputSchema"]),
            "annotations": (runtime_annotations, record["annotations"]),
        }
        for field, (actual, wanted) in comparisons.items():
            if actual != wanted:
                failures.append(f"Runtime {field} drifted for {tool.name}")
    return failures


def validate_file(path: Path, expected: dict[str, Any], label: str) -> list[str]:
    if not path.exists():
        return [f"Missing {label}: {path.relative_to(ROOT)}"]
    if json.loads(path.read_text(encoding="utf-8")) != expected:
        return [f"{label} drift. Run: python scripts/check_tool_contracts.py --update"]
    return []


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true")
    args = parser.parse_args()
    snapshot = build_snapshot()
    runtime_manifest = build_runtime_manifest(snapshot)
    failures = validate_static(snapshot)
    if args.update:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        RUNTIME_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(stable(snapshot), encoding="utf-8")
        RUNTIME_MANIFEST.write_text(stable(runtime_manifest), encoding="utf-8")
        print(f"Updated {SNAPSHOT.relative_to(ROOT)}")
        print(f"Updated {RUNTIME_MANIFEST.relative_to(ROOT)}")
        return 0 if not failures else 1

    failures.extend(validate_file(SNAPSHOT, snapshot, "MCP tool schema snapshot"))
    failures.extend(
        validate_file(RUNTIME_MANIFEST, runtime_manifest, "Runtime tool manifest")
    )
    failures.extend(await validate_runtime(snapshot))
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Tool contract checks passed: implementation schemas, runtime manifest, docs, tests, "
        "HTTP policy metadata, Studio mappings, and README tables are synchronized."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
