"""MCP 2025-11-25 protocol contract tests for the Fovux stdio server."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from fastmcp.client import StdioTransport
from fastmcp.exceptions import ToolError

from fovux import __version__
from fovux.core.tool_registry import list_tool_names
from fovux.server import mcp

_PROTOCOL_VERSION = "2025-11-25"
_TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.asyncio
@pytest.mark.contract
async def test_initialize_negotiates_mcp_2025_11_25_tools_capability() -> None:
    """Initialization should negotiate the current MCP revision and tool capability."""
    async with Client(mcp) as client:
        initialize_result = client.initialize_result

    assert initialize_result.protocolVersion == _PROTOCOL_VERSION
    assert initialize_result.serverInfo.name == "fovux"
    assert initialize_result.serverInfo.version == __version__
    assert initialize_result.capabilities.tools is not None
    assert initialize_result.capabilities.tools.listChanged is True
    assert initialize_result.capabilities.tasks is None


@pytest.mark.asyncio
@pytest.mark.contract
async def test_tools_list_returns_stable_valid_tool_schemas() -> None:
    """tools/list should expose every registered tool with valid object schemas."""
    async with Client(mcp) as client:
        tools = await client.list_tools()

    assert {tool.name for tool in tools} == set(list_tool_names())
    for tool in tools:
        assert _TOOL_NAME_PATTERN.fullmatch(tool.name)
        assert tool.description
        assert isinstance(tool.inputSchema, dict)
        assert tool.inputSchema["type"] == "object"
        assert tool.inputSchema is not None


@pytest.mark.asyncio
@pytest.mark.contract
async def test_tools_call_returns_structured_content_with_text_fallback(
    tmp_fovux_home: Path,
) -> None:
    """tools/call should return structured results and a text fallback."""
    assert tmp_fovux_home.is_dir()

    async with Client(mcp) as client:
        result = await client.call_tool("model_list", {})

    assert result.is_error is False
    assert result.structured_content == {"models": [], "total": 0, "offset": 0, "limit": 50}
    assert result.data == result.structured_content
    assert json.loads(result.content[0].text) == result.structured_content


@pytest.mark.asyncio
@pytest.mark.contract
async def test_unknown_tool_returns_protocol_tool_error() -> None:
    """Unknown tool calls should fail as protocol-level tool errors."""
    async with Client(mcp) as client:
        with pytest.raises(ToolError, match="Unknown tool"):
            await client.call_tool("ghost_tool", {})


@pytest.mark.asyncio
@pytest.mark.contract
async def test_stdio_cli_transport_initializes_lists_calls_and_shuts_down(
    tmp_fovux_home: Path,
    tmp_path: Path,
) -> None:
    """The installed CLI should work as an MCP stdio subprocess."""
    env = os.environ.copy()
    env["FOVUX_HOME"] = str(tmp_fovux_home)
    env["FASTMCP_CHECK_FOR_UPDATES"] = "off"
    log_file = tmp_path / "fovux-stdio.log"
    transport = StdioTransport(
        sys.executable,
        ["-m", "fovux.cli"],
        cwd=str(_PACKAGE_ROOT),
        env=env,
        log_file=log_file,
    )

    async with Client(transport, init_timeout=60) as client:
        tools = await client.list_tools()
        result = await client.call_tool("model_list", {})
        initialize_result = client.initialize_result

    assert initialize_result.protocolVersion == _PROTOCOL_VERSION
    assert len(tools) == len(list_tool_names())
    assert result.is_error is False
    assert result.structured_content["total"] == 0


@pytest.mark.contract
def test_studio_http_bridge_is_not_mcp_streamable_http_contract(tmp_fovux_home: Path) -> None:
    """The HTTP path should remain the authenticated Studio bridge, not MCP HTTP."""
    from fastapi.testclient import TestClient

    from fovux.http.app import create_app

    with TestClient(create_app()) as client:
        client.app.state.nonlocal_bind_allowed = True
        token = str(client.app.state.auth_token)
        headers = {"Authorization": f"Bearer {token}"}
        health = client.get("/health")
        unauthorized = client.get("/runs")
        tool_response = client.post("/tools/model_list", json={}, headers=headers)

    assert health.status_code == 200
    assert health.json()["service"] == "fovux-mcp"
    assert unauthorized.status_code == 401
    assert tool_response.status_code == 200
    assert tool_response.json()["total"] == 0
