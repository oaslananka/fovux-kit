"""Unit tests for the central tool registry."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from fovux.core.tool_registry import available_tools, list_tool_names, register_all, resolve_tool


def test_available_tools_lists_known_entries() -> None:
    """The registry should expose the supported HTTP tool names."""
    tools = available_tools()

    assert "annotation_quality_check" in tools
    assert "dataset_inspect" in tools
    assert "fovux_doctor" in tools
    assert "infer_batch" in tools
    assert "model_profile" in tools
    assert "train_start" in tools
    assert tools == sorted(tools)


def test_list_tool_names_is_available_tools_alias() -> None:
    """Release tooling should have a stable semantic tool-list helper."""
    assert list_tool_names() == available_tools()
    assert len(list_tool_names()) == 36


def test_resolve_tool_imports_and_returns_callable() -> None:
    """resolve_tool should load the target module and return the named function."""
    tool = resolve_tool("model_list")

    assert callable(tool)
    assert tool.__name__ == "model_list"


def test_resolve_tool_unknown_name_raises_key_error() -> None:
    """Unknown tool names should fail fast."""
    with pytest.raises(KeyError):
        resolve_tool("ghost_tool")


def test_register_all_imports_all_tool_modules() -> None:
    """register_all should import every tool module in the registry."""
    imported: list[str] = []

    with patch("fovux.core.tool_registry.importlib.import_module") as import_module:
        import_module.side_effect = lambda name: imported.append(name)
        register_all()

    assert imported
    assert "fovux.tools.dataset_inspect" in imported
    assert "fovux.tools.train_stop" in imported
