# MCP Client Compatibility Matrix

Fovux supports MCP through stdio. The Fovux Studio local API is a separate REST/SSE bridge and is not the MCP Streamable HTTP endpoint.

## Automated matrix

| Client / host | OS | Transport | Install method | Smoke command | Status | Known limitations |
| --- | --- | --- | --- | --- | --- | --- |
| Raw JSON-RPC stdio | Linux CI/local | stdio | `uv run --project fovux-mcp fovux-mcp` | `uv run pytest tests/contract/test_mcp_protocol.py` | Verified | Protocol shape only. |
| FastMCP client | Linux CI/local | in-process | `uv sync --extra dev` | `uv run pytest -m contract` | Verified | Host substitute only. |
| Fovux Studio | Windows/macOS/Linux | Studio API + LM tools | `.vsix` or dev host | `npm test` | Verified | Studio API is separate from MCP HTTP. |

## Startup reliability

The production command dispatches arg-free `fovux-mcp` sessions through `fovux.stdio`, avoiding the
interactive Typer/Rich CLI import path. Raw initialization has a 25-second startup budget. Set
`FOVUX_STARTUP_DIAGNOSTICS=1` to emit bounded JSON stage timings to stderr; MCP stdout remains
reserved for JSON-RPC. Scheduled CI runs `scripts/check_stdio_startup.py` for three consecutive
initializations to detect cold-start regressions.

## Manual GUI checklist

1. Install the current `fovux-mcp` package.
2. Configure the host command as `fovux-mcp` with no arguments.
3. Confirm initialization succeeds.
4. Confirm all 47 MCP tools are visible.
5. Call `model_list` with `{}` and verify a structured response.
6. Call an unknown tool and verify the host shows a tool error.
7. Record host version, OS, transport, install method, smoke result, and limitations.

## Manual tracking table

| Client / host | OS | Transport | Install method | Smoke command / checklist | Status | Known limitations |
| --- | --- | --- | --- | --- | --- | --- |
| Claude Desktop | macOS/Windows | stdio | User MCP config | Manual GUI checklist | Manual pending | Host UI approval flow varies by version. |
| VS Code MCP host | Windows/macOS/Linux | stdio | Workspace/user `mcp.json` | Manual GUI checklist | Manual pending | Separate from Fovux Studio LM tools. |
| Generic hosted MCP client | Web/desktop | host-specific | Host-specific connector setup | Manual GUI checklist | Manual pending | Hosted use needs a separate server auth design. |
| MCP Inspector / dev client | Linux/macOS/Windows | stdio | Local command | Manual GUI checklist | Manual pending | Development inspection only. |

## Release evidence

Each release should include raw JSON-RPC output, FastMCP contract output, Studio extension test output, manual GUI rows when verified, known limitations, and follow-up issue numbers.
