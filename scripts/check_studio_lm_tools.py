"""Validate generated VS Code Language Model Tool metadata and backend mapping."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MCP_ROOT = ROOT / "fovux-mcp"
STUDIO_ROOT = ROOT / "fovux-studio"
SRC = MCP_ROOT / "src"
GENERATOR_PATH = ROOT / "scripts" / "generate_studio_lm_tools.py"
SNAPSHOT_PATH = MCP_ROOT / "tests" / "snapshots" / "mcp_tool_schemas.json"
OVERRIDES_PATH = STUDIO_ROOT / "src" / "fovux" / "tools" / "overrides.json"
PACKAGE_PATH = STUDIO_ROOT / "package.json"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fovux.core.tool_registry import list_tool_names  # noqa: E402

NAME_RE = re.compile(r"^fovux_[a-z]+_[a-z0-9_]+$")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(_read(path))
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a JSON object")
    return value


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_studio_lm_tools", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load Studio LM tool generator")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    """Run semantic mapping, generated-artifact, package, policy, and docs checks."""
    failures: list[str] = []
    generated_tools: list[dict[str, Any]] = []
    expected_package: dict[str, Any] = {}
    package: dict[str, Any] = {}
    snapshot: dict[str, Any] = {}

    try:
        generator = _load_generator()
        snapshot = _json(SNAPSHOT_PATH)
        overrides = _json(OVERRIDES_PATH)
        package = _json(PACKAGE_PATH)
        generated_tools, expected_package = generator.build_generated_artifacts(
            snapshot, overrides, package
        )
        generator.generate(check=True)
    except (OSError, ValueError, RuntimeError) as exc:
        failures.append(f"Studio LM generation contract failed: {exc}")

    if package and expected_package:
        actual_contributes = package.get("contributes")
        expected_contributes = expected_package.get("contributes")
        if not isinstance(actual_contributes, dict) or not isinstance(expected_contributes, dict):
            failures.append("package.json contributes must be an object")
        elif actual_contributes.get("languageModelTools") != expected_contributes.get(
            "languageModelTools"
        ):
            failures.append(
                "package.json Language Model tools differ from generated snapshot metadata"
            )

    backend = set(list_tool_names())
    mapped_backend: set[str] = set()
    names: set[str] = set()
    references: set[str] = set()
    for tool in generated_tools:
        name = tool.get("name")
        reference = tool.get("toolReferenceName")
        mcp_name = tool.get("mcpToolName")
        if not isinstance(name, str) or not NAME_RE.fullmatch(name):
            failures.append(f"LM tool name must follow fovux_{{verb}}_{{noun}}: {name}")
        elif name in names:
            failures.append(f"Duplicate LM tool contribution name: {name}")
        else:
            names.add(name)
        if not isinstance(reference, str) or not reference.startswith("fovux_"):
            failures.append(f"{name} has invalid toolReferenceName")
        elif reference in references:
            failures.append(f"Duplicate LM prompt reference name: {reference}")
        else:
            references.add(reference)
        for field in ("displayName", "modelDescription", "userDescription"):
            value = tool.get(field)
            if not isinstance(value, str) or not value.strip():
                failures.append(f"{name} missing generated field {field}")
        if len(str(tool.get("modelDescription", ""))) < 80:
            failures.append(f"{name} modelDescription is too short for LLM routing")
        schema = tool.get("inputSchema")
        if not isinstance(schema, dict) or schema.get("type") != "object":
            failures.append(f"{name} inputSchema must be an object schema")
        if not isinstance(tool.get("requiresConfirmation"), bool):
            failures.append(f"{name} requiresConfirmation must be generated from policy")
        if not isinstance(tool.get("requiredScope"), str):
            failures.append(f"{name} requiredScope must be generated from policy")
        if not isinstance(mcp_name, str) or mcp_name not in backend:
            failures.append(f"{name} maps to unknown backend tool {mcp_name}")
        else:
            mapped_backend.add(mcp_name)

    snapshot_mappings = snapshot.get("studio_mcp_mappings") if snapshot else None
    if not isinstance(snapshot_mappings, list) or any(
        not isinstance(name, str) for name in snapshot_mappings
    ):
        failures.append("Snapshot Studio MCP mappings must be a string array")
    elif mapped_backend != set(snapshot_mappings):
        failures.append("Generated Studio mapping set differs from snapshot Studio MCP mappings")

    if generated_tools and snapshot.get("studio_lm_tool_count") != len(generated_tools):
        failures.append("Generated Studio LM tool count differs from snapshot count")

    package_tools: object = None
    if package:
        contributes = package.get("contributes")
        if isinstance(contributes, dict):
            package_tools = contributes.get("languageModelTools")
    if not isinstance(package_tools, list):
        failures.append("package.json languageModelTools must be an array")
    else:
        generic = [
            tool
            for tool in package_tools
            if isinstance(tool, dict) and tool.get("name") == "fovux_call_tool"
        ]
        if len(generic) != 1:
            failures.append("Generic fovux_call_tool fallback must remain exactly once")

    docs = _read(ROOT / "docs" / "studio-language-model-tools.md")
    for phrase in (
        "fovux_{verb}_{noun}",
        "userDescription",
        "modelDescription",
        "prepareInvocation",
        "mcp_tool_schemas.json",
        "overrides.json",
        "task studio:lm-tools:generate",
        "task studio:lm-tools:check",
        "generic `fovux_call_tool` fallback",
        "Backend tools not directly exposed",
        "Active-learning queue tools",
        "Runtime-heavy live streams",
    ):
        if phrase not in docs:
            failures.append(f"Studio LM tools doc missing phrase: {phrase}")

    if generated_tools and not (backend - mapped_backend):
        failures.append(
            "Expected a documented curated subset; all backend tools are exposed unexpectedly"
        )

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Studio LM tool checks passed: canonical schemas, generated artifacts, policy metadata, "
        "package contributions, mappings, fallback, and docs are aligned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
