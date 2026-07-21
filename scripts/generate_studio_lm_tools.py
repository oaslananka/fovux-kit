"""Generate Studio Language Model tool definitions from the backend schema snapshot."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = ROOT / "fovux-mcp" / "tests" / "snapshots" / "mcp_tool_schemas.json"
STUDIO_ROOT = ROOT / "fovux-studio"
OVERRIDES_PATH = STUDIO_ROOT / "src" / "fovux" / "tools" / "overrides.json"
DEFINITIONS_PATH = STUDIO_ROOT / "src" / "fovux" / "tools" / "definitions.ts"
PACKAGE_PATH = STUDIO_ROOT / "package.json"
PRETTIER_SCRIPT = STUDIO_ROOT / "node_modules" / "prettier" / "bin" / "prettier.cjs"

NAME_PATTERN = re.compile(r"fovux_[a-z]+_[a-z0-9_]+")
SCHEMA_TYPES = {"array", "boolean", "integer", "null", "number", "object", "string"}
SCHEMA_KEYWORDS = {
    "additionalProperties",
    "anyOf",
    "default",
    "description",
    "enum",
    "examples",
    "items",
    "maximum",
    "maxItems",
    "minimum",
    "minItems",
    "properties",
    "required",
    "title",
    "type",
}
REQUIRED_OVERRIDE_FIELDS = {
    "name",
    "toolReferenceName",
    "displayName",
    "userDescription",
    "modelDescription",
    "tags",
    "canBeReferencedInPrompt",
}
OPTIONAL_OVERRIDE_FIELDS = {"confirmationKind"}
CUSTOM_CONFIRMATION_KINDS = {
    "export_onnx",
    "export_tflite",
    "quantize_int8",
    "run_delete",
    "run_tag",
    "train_resume",
    "train_start",
    "train_stop",
}


def _json_object(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return cast(dict[str, Any], value)


def _json_array(value: object, *, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a JSON array")
    return value


def _validate_schema(schema: object, *, path: str) -> dict[str, Any]:
    value = _json_object(schema, label=path)
    unsupported = sorted(set(value) - SCHEMA_KEYWORDS)
    if unsupported:
        raise ValueError(
            f"{path} uses unsupported JSON Schema keyword(s): {', '.join(unsupported)}"
        )

    schema_type = value.get("type")
    if schema_type is not None and schema_type not in SCHEMA_TYPES:
        raise ValueError(f"{path}.type is unsupported: {schema_type!r}")

    properties = value.get("properties")
    if properties is not None:
        property_map = _json_object(properties, label=f"{path}.properties")
        for name, child in property_map.items():
            _validate_schema(child, path=f"{path}.properties.{name}")

    items = value.get("items")
    if items is not None:
        _validate_schema(items, path=f"{path}.items")

    any_of = value.get("anyOf")
    if any_of is not None:
        choices = _json_array(any_of, label=f"{path}.anyOf")
        if not choices:
            raise ValueError(f"{path}.anyOf must not be empty")
        for index, child in enumerate(choices):
            _validate_schema(child, path=f"{path}.anyOf[{index}]")

    additional = value.get("additionalProperties")
    if additional is not None and not isinstance(additional, bool):
        _validate_schema(additional, path=f"{path}.additionalProperties")

    required = value.get("required")
    if required is not None:
        names = _json_array(required, label=f"{path}.required")
        if any(not isinstance(name, str) for name in names):
            raise ValueError(f"{path}.required must contain only strings")

    if path.endswith(".inputSchema") and schema_type != "object":
        raise ValueError(f"{path} must be an object schema")
    return deepcopy(value)


def _validate_override(name: str, raw: object, *, requires_confirmation: bool) -> dict[str, Any]:
    override = _json_object(raw, label=f"overrides.tools.{name}")
    fields = set(override)
    missing = sorted(REQUIRED_OVERRIDE_FIELDS - fields)
    unsupported = sorted(fields - REQUIRED_OVERRIDE_FIELDS - OPTIONAL_OVERRIDE_FIELDS)
    if missing:
        raise ValueError(f"{name} override is missing fields: {', '.join(missing)}")
    if unsupported:
        raise ValueError(f"{name} has unsupported override fields: {', '.join(unsupported)}")

    tool_name = override.get("name")
    if not isinstance(tool_name, str) or not NAME_PATTERN.fullmatch(tool_name):
        raise ValueError(f"{name} override has invalid LM tool name: {tool_name!r}")
    reference = override.get("toolReferenceName")
    if not isinstance(reference, str) or not reference.startswith("fovux_"):
        raise ValueError(f"{name} override has invalid toolReferenceName")
    for field in ("displayName", "userDescription", "modelDescription"):
        value = override.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} override field {field} must be non-empty")
    if len(cast(str, override["modelDescription"])) < 80:
        raise ValueError(f"{name} modelDescription is too short for LLM routing")

    tags = override.get("tags")
    if (
        not isinstance(tags, list)
        or not tags
        or any(not isinstance(tag, str) or not tag for tag in tags)
    ):
        raise ValueError(f"{name} override tags must be non-empty strings")
    if not isinstance(override.get("canBeReferencedInPrompt"), bool):
        raise ValueError(f"{name} canBeReferencedInPrompt must be boolean")

    confirmation = override.get("confirmationKind")
    if confirmation is not None:
        if confirmation not in CUSTOM_CONFIRMATION_KINDS:
            raise ValueError(f"{name} has unsupported confirmationKind {confirmation!r}")
        if confirmation != name:
            raise ValueError(f"{name} confirmationKind must match its backend tool name")
        if not requires_confirmation:
            raise ValueError(f"{name} cannot define confirmation copy for a read-only tool")
    return deepcopy(override)


def build_generated_artifacts(
    snapshot_raw: object,
    overrides_raw: object,
    package_raw: object,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Build generated TypeScript definitions and package metadata as pure data."""
    snapshot = _json_object(snapshot_raw, label="schema snapshot")
    overrides = _json_object(overrides_raw, label="Studio LM overrides")
    package = deepcopy(_json_object(package_raw, label="Studio package.json"))

    if overrides.get("schemaVersion") != 1:
        raise ValueError("Studio LM overrides schemaVersion must be 1")
    override_tools = _json_object(overrides.get("tools"), label="overrides.tools")

    mappings = _json_array(
        snapshot.get("studio_mcp_mappings"), label="snapshot.studio_mcp_mappings"
    )
    if any(not isinstance(name, str) for name in mappings):
        raise ValueError("snapshot.studio_mcp_mappings must contain strings")
    mapping_names = cast(list[str], mappings)
    if snapshot.get("studio_only_tools") != []:
        raise ValueError("Studio-only tools require an explicit generator model")
    if snapshot.get("studio_lm_tool_count") != len(mapping_names):
        raise ValueError("snapshot Studio LM tool count does not match its mappings")
    if set(mapping_names) != set(override_tools):
        missing = sorted(set(mapping_names) - set(override_tools))
        extra = sorted(set(override_tools) - set(mapping_names))
        raise ValueError(f"Studio LM override mapping drift: missing={missing}, extra={extra}")

    snapshot_tools: dict[str, dict[str, Any]] = {}
    for raw_tool in _json_array(snapshot.get("tools"), label="snapshot.tools"):
        tool = _json_object(raw_tool, label="snapshot tool")
        name = tool.get("name")
        if not isinstance(name, str):
            raise ValueError("snapshot tool name must be a string")
        snapshot_tools[name] = tool

    generated: list[dict[str, Any]] = []
    names: set[str] = set()
    references: set[str] = set()
    for mcp_name, raw_override in override_tools.items():
        backend = snapshot_tools.get(mcp_name)
        if backend is None:
            raise ValueError(f"Studio LM override maps unknown backend tool {mcp_name}")
        policy = _json_object(backend.get("http_policy"), label=f"{mcp_name}.http_policy")
        requires_confirmation = policy.get("requires_confirmation")
        required_scope = policy.get("required_scope")
        category = policy.get("category")
        if not isinstance(requires_confirmation, bool):
            raise ValueError(f"{mcp_name} policy requires_confirmation must be boolean")
        if not isinstance(required_scope, str) or not isinstance(category, str):
            raise ValueError(f"{mcp_name} policy scope/category must be strings")

        override = _validate_override(
            mcp_name, raw_override, requires_confirmation=requires_confirmation
        )
        tool_name = cast(str, override["name"])
        reference = cast(str, override["toolReferenceName"])
        if tool_name in names or reference in references:
            raise ValueError(f"duplicate Studio LM name/reference for {mcp_name}")
        names.add(tool_name)
        references.add(reference)

        tool = {
            **override,
            "mcpToolName": mcp_name,
            "inputSchema": _validate_schema(
                backend.get("inputSchema"), path=f"{mcp_name}.inputSchema"
            ),
            "requiresConfirmation": requires_confirmation,
            "requiredScope": required_scope,
            "policyCategory": category,
        }
        generated.append(tool)

    contributes = _json_object(package.get("contributes"), label="package.contributes")
    package_tools = _json_array(
        contributes.get("languageModelTools"),
        label="package.contributes.languageModelTools",
    )
    generic = [
        tool
        for tool in package_tools
        if isinstance(tool, dict) and tool.get("name") == "fovux_call_tool"
    ]
    if len(generic) != 1:
        raise ValueError("package.json must contain exactly one generic fovux_call_tool")

    generated_package_tools: list[dict[str, Any]] = [deepcopy(cast(dict[str, Any], generic[0]))]
    for tool in generated:
        package_tool: dict[str, Any] = {
            "name": tool["name"],
            "toolReferenceName": tool["toolReferenceName"],
            "displayName": tool["displayName"],
            "modelDescription": tool["modelDescription"],
            "tags": ["fovux", *cast(list[str], tool["tags"])],
            "inputSchema": deepcopy(tool["inputSchema"]),
            "userDescription": tool["userDescription"],
        }
        if tool["canBeReferencedInPrompt"]:
            package_tool["canBeReferencedInPrompt"] = True
        generated_package_tools.append(package_tool)
    contributes["languageModelTools"] = generated_package_tools
    return generated, package


def _load_json(path: Path) -> dict[str, Any]:
    return _json_object(json.loads(path.read_text(encoding="utf-8")), label=str(path))


def _format_typescript(source: str) -> str:
    node = shutil.which("node")
    if node is None or not PRETTIER_SCRIPT.is_file():
        raise RuntimeError("Node and fovux-studio Prettier dependencies are required")
    # Node comes from PATH and the executed Prettier script is a fixed repository dependency.
    completed = subprocess.run(  # noqa: S603
        [node, str(PRETTIER_SCRIPT), "--parser", "typescript"],
        cwd=STUDIO_ROOT,
        input=source,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Prettier failed: {completed.stderr.strip()}")
    return completed.stdout


def _render_definitions(tools: list[dict[str, Any]]) -> str:
    payload = json.dumps(tools, indent=2, ensure_ascii=False)
    source = f"""/**
 * GENERATED FILE. Run `task studio:lm-tools:generate` after backend schema changes.
 * Source: fovux-mcp/tests/snapshots/mcp_tool_schemas.json
 * Overrides: fovux-studio/src/fovux/tools/overrides.json
 */
import type {{ GranularToolDefinition }} from "./types";

export const GRANULAR_TOOLS = {payload} satisfies GranularToolDefinition[];
"""
    return _format_typescript(source)


def _render_package(package: dict[str, Any]) -> str:
    return json.dumps(package, indent=2, ensure_ascii=False) + "\n"


def _write_or_check(path: Path, expected: str, *, check: bool) -> bool:
    current = path.read_text(encoding="utf-8") if path.is_file() else ""
    if current == expected:
        return False
    if check:
        raise ValueError(f"generated artifact is stale: {path.relative_to(ROOT)}")
    path.write_text(expected, encoding="utf-8")
    return True


def generate(*, check: bool) -> list[Path]:
    """Generate or verify fixed Studio LM artifacts."""
    tools, package = build_generated_artifacts(
        _load_json(SNAPSHOT_PATH),
        _load_json(OVERRIDES_PATH),
        _load_json(PACKAGE_PATH),
    )
    changed: list[Path] = []
    if _write_or_check(DEFINITIONS_PATH, _render_definitions(tools), check=check):
        changed.append(DEFINITIONS_PATH)
    if _write_or_check(PACKAGE_PATH, _render_package(package), check=check):
        changed.append(PACKAGE_PATH)
    return changed


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when generated files differ")
    return parser.parse_args()


def main() -> int:
    """Generate Studio LM tool artifacts or verify they are current."""
    args = _parse_args()
    try:
        changed = generate(check=args.check)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1
    if args.check:
        print("Studio LM generated artifacts are current.")
    elif changed:
        print("Updated Studio LM generated artifacts:")
        for path in changed:
            print(f"- {path.relative_to(ROOT)}")
    else:
        print("Studio LM generated artifacts already current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
