"""Contract tests for generated Studio Language Model tool definitions."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "generate_studio_lm_tools.py"
SNAPSHOT = ROOT / "fovux-mcp" / "tests" / "snapshots" / "mcp_tool_schemas.json"
OVERRIDES = ROOT / "fovux-studio" / "src" / "fovux" / "tools" / "overrides.json"
PACKAGE = ROOT / "fovux-studio" / "package.json"


def _load_module() -> ModuleType:
    assert SCRIPT.exists(), "Studio LM tool generator is missing"
    spec = importlib.util.spec_from_file_location("generate_studio_lm_tools", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _documents() -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    return (
        json.loads(SNAPSHOT.read_text(encoding="utf-8")),
        json.loads(OVERRIDES.read_text(encoding="utf-8")),
        json.loads(PACKAGE.read_text(encoding="utf-8")),
    )


def test_generated_tools_use_canonical_snapshot_schemas_and_policy() -> None:
    module = _load_module()
    snapshot, overrides, package = _documents()

    tools, _ = module.build_generated_artifacts(snapshot, overrides, package)
    snapshot_tools = {item["name"]: item for item in snapshot["tools"]}

    assert [tool["mcpToolName"] for tool in tools] == list(overrides["tools"])
    assert len(tools) == snapshot["studio_lm_tool_count"] == 20
    for tool in tools:
        backend = snapshot_tools[tool["mcpToolName"]]
        assert tool["inputSchema"] == backend["inputSchema"]
        assert tool["requiresConfirmation"] is backend["http_policy"]["requires_confirmation"]
        assert tool["requiredScope"] == backend["http_policy"]["required_scope"]

    assert (
        next(tool for tool in tools if tool["mcpToolName"] == "train_start")["confirmationKind"]
        == "train_start"
    )
    assert not next(tool for tool in tools if tool["mcpToolName"] == "dataset_inspect")[
        "requiresConfirmation"
    ]


def test_generator_rejects_schema_fields_in_studio_overrides() -> None:
    module = _load_module()
    snapshot, overrides, package = _documents()
    invalid = copy.deepcopy(overrides)
    invalid["tools"]["dataset_inspect"]["inputSchema"] = {"type": "object"}

    with pytest.raises(ValueError, match="unsupported override fields"):
        module.build_generated_artifacts(snapshot, invalid, package)


def test_generator_rejects_unsupported_backend_schema_constructs() -> None:
    module = _load_module()
    snapshot, overrides, package = _documents()
    invalid = copy.deepcopy(snapshot)
    dataset = next(tool for tool in invalid["tools"] if tool["name"] == "dataset_inspect")
    dataset["inputSchema"]["oneOf"] = [{"type": "object"}]

    with pytest.raises(ValueError, match="unsupported JSON Schema keyword"):
        module.build_generated_artifacts(invalid, overrides, package)


def test_generation_is_deterministic_and_preserves_generic_fallback() -> None:
    module = _load_module()
    snapshot, overrides, package = _documents()

    first_tools, first_package = module.build_generated_artifacts(snapshot, overrides, package)
    second_tools, second_package = module.build_generated_artifacts(snapshot, overrides, package)

    assert second_tools == first_tools
    assert second_package == first_package
    package_tools = first_package["contributes"]["languageModelTools"]
    assert package_tools[0]["name"] == "fovux_call_tool"
    assert [tool["name"] for tool in package_tools[1:]] == [tool["name"] for tool in first_tools]
