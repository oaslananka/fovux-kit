"""MCP 2025-11-25 protocol contract tests for the Fovux stdio server."""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

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
# Startup is optimized for a 25-second initialization budget; the read timeout leaves
# a small diagnostics window without masking regressions by increasing the budget.
_STDIO_INITIALIZE_BUDGET_SECONDS = 25.0
_READ_TIMEOUT_SECONDS = 30.0


@asynccontextmanager
async def _stdio_process(tmp_fovux_home: Path) -> AsyncIterator[asyncio.subprocess.Process]:
    """Start the production stdio entry point as a raw MCP subprocess."""
    env = os.environ.copy()
    env["FOVUX_HOME"] = str(tmp_fovux_home)
    env["FASTMCP_CHECK_FOR_UPDATES"] = "off"
    env["FOVUX_STARTUP_DIAGNOSTICS"] = "1"
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "fovux.stdio",
        cwd=str(_PACKAGE_ROOT),
        env=env,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=sys.platform != "win32",
    )
    try:
        yield process
    finally:
        await _stop_process(process)


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    """Stop the whole stdio process group so timeout paths do not leak workers."""
    if process.stdin is not None and not process.stdin.is_closing():
        process.stdin.close()
    try:
        await asyncio.wait_for(process.wait(), timeout=3)
        return
    except TimeoutError:
        pass
    if sys.platform != "win32":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    else:
        process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=3)
        return
    except TimeoutError:
        pass
    if sys.platform != "win32":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        process.kill()
    await process.wait()


def _jsonrpc_request(request_id: int, method: str, params: dict[str, object]) -> dict[str, object]:
    """Create a JSON-RPC request payload."""
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}


async def _send_jsonrpc(
    process: asyncio.subprocess.Process,
    payload: dict[str, object],
) -> None:
    """Send one newline-delimited JSON-RPC message."""
    assert process.stdin is not None
    process.stdin.write(json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n")
    await process.stdin.drain()


async def _stderr_tail(process: asyncio.subprocess.Process) -> str:
    """Return a bounded best-effort stderr tail for failed raw stdio tests."""
    if process.stderr is None:
        return ""
    chunks: list[bytes] = []
    for _ in range(4):
        try:
            chunk = await asyncio.wait_for(process.stderr.read(1024), timeout=0.05)
        except TimeoutError:
            break
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")[-4000:]


def _linux_process_snapshot(process: asyncio.subprocess.Process) -> str:
    """Return bounded Linux process state without introducing a psutil dependency."""
    if sys.platform != "linux":
        return "unavailable"
    details: list[str] = []
    for name in ("status", "wchan"):
        path = Path(f"/proc/{process.pid}/{name}")
        try:
            value = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        details.append(f"{name}={value[:1500].strip()}")
    return " | ".join(details) or "process-exited"


async def _read_jsonrpc(
    process: asyncio.subprocess.Process,
    *,
    phase: str,
    started_at: float | None = None,
) -> dict[str, Any]:
    """Read one response and raise an actionable bounded diagnostic on failure."""
    assert process.stdout is not None
    read_started_at = started_at if started_at is not None else time.monotonic()
    try:
        line = await asyncio.wait_for(process.stdout.readline(), timeout=_READ_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        elapsed = time.monotonic() - read_started_at
        stderr = await _stderr_tail(process)
        snapshot = _linux_process_snapshot(process)
        raise AssertionError(
            f"MCP stdio {phase} timed out after {elapsed:.3f}s; "
            f"pid={process.pid}; returncode={process.returncode}; "
            f"process={snapshot}; stderr_tail={stderr!r}"
        ) from exc
    if not line:
        stderr = await _stderr_tail(process)
        raise AssertionError(
            f"MCP stdio server exited during {phase}; returncode={process.returncode}; "
            f"stderr_tail={stderr!r}"
        )
    return json.loads(line.decode("utf-8"))


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
async def test_raw_stdio_jsonrpc_initialize_list_call_error_and_cancel(
    tmp_fovux_home: Path,
) -> None:
    """Raw stdio JSON-RPC should cover initialize, tools, errors, and cancellation."""
    async with _stdio_process(tmp_fovux_home) as process:
        initialize = _jsonrpc_request(
            1,
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "fovux-contract", "version": "0.0.0"},
            },
        )
        init_started_at = time.monotonic()
        await _send_jsonrpc(process, initialize)
        init_response = await _read_jsonrpc(process, phase="initialize", started_at=init_started_at)
        init_elapsed = time.monotonic() - init_started_at
        assert init_elapsed < _STDIO_INITIALIZE_BUDGET_SECONDS, (
            f"stdio initialize exceeded {_STDIO_INITIALIZE_BUDGET_SECONDS:.0f}s budget: "
            f"{init_elapsed:.3f}s; stderr={await _stderr_tail(process)!r}"
        )
        assert init_response.get("jsonrpc") == "2.0", await _stderr_tail(process)
        assert init_response.get("id") == 1
        init_result = init_response["result"]
        assert init_result["protocolVersion"] == _PROTOCOL_VERSION
        assert init_result["serverInfo"] == {"name": "fovux", "version": __version__}
        assert init_result["capabilities"]["tools"]["listChanged"] is True

        await _send_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )

        await _send_jsonrpc(process, _jsonrpc_request(2, "tools/list", {}))
        list_response = await _read_jsonrpc(process, phase="tools/list")
        assert list_response.get("id") == 2
        list_result = list_response["result"]
        assert list_result.get("nextCursor") in (None, "")
        tools = list_result["tools"]
        assert {tool["name"] for tool in tools} == set(list_tool_names())
        for tool in tools:
            assert _TOOL_NAME_PATTERN.fullmatch(tool["name"])
            assert tool["description"]
            assert tool["inputSchema"]["type"] == "object"
            if "outputSchema" in tool:
                assert tool["outputSchema"]["type"] == "object"
            if tool.get("annotations") is not None:
                assert isinstance(tool["annotations"], dict)

        await _send_jsonrpc(
            process,
            _jsonrpc_request(3, "tools/call", {"name": "model_list", "arguments": {}}),
        )
        call_response = await _read_jsonrpc(process, phase="model_list tools/call")
        assert call_response.get("id") == 3
        call_result = call_response["result"]
        assert call_result.get("isError", False) is False
        assert call_result["structuredContent"] == {
            "models": [],
            "total": 0,
            "offset": 0,
            "limit": 50,
        }
        assert json.loads(call_result["content"][0]["text"]) == call_result["structuredContent"]

        await _send_jsonrpc(
            process,
            _jsonrpc_request(4, "tools/call", {"name": "ghost_tool", "arguments": {}}),
        )
        tool_error_response = await _read_jsonrpc(process, phase="unknown tools/call")
        assert tool_error_response.get("id") == 4
        tool_error_result = tool_error_response["result"]
        assert tool_error_result["isError"] is True
        assert "Unknown tool" in tool_error_result["content"][0]["text"]

        await _send_jsonrpc(process, _jsonrpc_request(5, "fovux/unknown_method", {}))
        method_error_response = await _read_jsonrpc(process, phase="unknown method")
        assert method_error_response.get("id") == 5
        assert "error" in method_error_response
        assert method_error_response["error"]["code"] < 0

        await _send_jsonrpc(
            process,
            {
                "jsonrpc": "2.0",
                "method": "notifications/cancelled",
                "params": {"requestId": 999, "reason": "contract test"},
            },
        )
        await _send_jsonrpc(process, _jsonrpc_request(6, "tools/list", {}))
        after_cancel_response = await _read_jsonrpc(process, phase="post-cancel tools/list")
        assert after_cancel_response.get("id") == 6
        assert len(after_cancel_response["result"]["tools"]) == len(list_tool_names())


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
        if tool.title is not None:
            assert tool.title.strip()
        assert isinstance(tool.inputSchema, dict)
        assert tool.inputSchema["type"] == "object"
        assert isinstance(tool.inputSchema.get("properties", {}), dict)
        if tool.outputSchema is not None:
            assert isinstance(tool.outputSchema, dict)
            assert tool.outputSchema["type"] == "object"
        if tool.annotations is not None:
            assert tool.annotations.model_dump(mode="json")


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
    from starlette.testclient import TestClient

    from fovux.http.app import create_app

    with TestClient(create_app()) as client:
        client.app.state.nonlocal_bind_allowed = True
        token = str(client.app.state.auth_token)
        headers = {"Authorization": f"Bearer {token}"}
        health = client.get("/health")
        unauthorized = client.get("/runs")
        tool_response = client.post("/tools/model_list", json={}, headers=headers)
        mcp_post_response = client.post(
            "/mcp",
            json=_jsonrpc_request(1, "initialize", {"protocolVersion": _PROTOCOL_VERSION}),
            headers={
                **headers,
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
                "MCP-Protocol-Version": _PROTOCOL_VERSION,
            },
        )
        mcp_get_response = client.get(
            "/mcp",
            headers={
                **headers,
                "Accept": "text/event-stream",
                "Mcp-Session-Id": "contract-test",
                "MCP-Protocol-Version": _PROTOCOL_VERSION,
            },
        )

    assert health.status_code == 200
    assert health.json()["service"] == "fovux-mcp"
    assert unauthorized.status_code == 401
    assert tool_response.status_code == 200
    assert tool_response.json()["total"] == 0
    assert mcp_post_response.status_code == 404
    assert mcp_get_response.status_code == 404
