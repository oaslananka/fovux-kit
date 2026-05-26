"""Integration test: MCP server handshake."""

from __future__ import annotations

from fovux.core.tool_registry import list_tool_names
from fovux.server import mcp


def test_mcp_server_has_name() -> None:
    """MCP server should have the correct name."""
    assert mcp.name == "fovux"


def test_mcp_server_has_version() -> None:
    """MCP server should report a version."""
    from fovux import __version__

    assert mcp.version == __version__


def test_mcp_server_has_tools() -> None:
    """MCP server should register every release tool with basic metadata."""
    tools = list_tool_names()

    assert len(tools) == 36
    assert {
        "active_learning_select",
        "dataset_augment",
        "distill_model",
        "infer_ensemble",
        "model_compare_visual",
        "run_archive",
        "sync_to_mlflow",
        "train_adjust",
    }.issubset(set(tools))
    for tool_name in tools:
        assert tool_name
        assert "_" in tool_name or tool_name.startswith("fovux")
    assert mcp.name == "fovux"
