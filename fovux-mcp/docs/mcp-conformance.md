# MCP 2025-11-25 Conformance

This checklist records the Fovux MCP surface for protocol revision `2025-11-25`.
It separates the stdio MCP server from the local Studio HTTP bridge so MCP
clients do not treat the Studio API as Streamable HTTP.

## Source Verification

Checked on 2026-06-03:

- MCP specification `2025-11-25`: lifecycle, transports, tools, roots, sampling,
  elicitation, schema, and changelog pages at `modelcontextprotocol.io`.
- FastMCP documentation for stdio and HTTP transports, `mcp.run()`,
  `mcp.run(show_banner=False)`, and CLI display settings.
- Installed package: `fastmcp 3.3.1`.

## Conformance Checklist

| Surface                        | Status           | Evidence                                                                           |
| ------------------------------ | ---------------- | ---------------------------------------------------------------------------------- |
| Protocol revision              | Supported        | FastMCP negotiates `2025-11-25` during `initialize`.                               |
| stdio transport                | Supported        | `fovux-mcp` with no subcommand starts the FastMCP stdio server.                    |
| Streamable HTTP transport      | Not exposed      | `fovux-mcp serve --http` is the Studio REST/SSE bridge, not an MCP endpoint.       |
| Lifecycle                      | Supported        | The stdio contract test initializes, lists tools, calls a tool, then closes.       |
| Tools capability               | Supported        | Server initialization advertises `capabilities.tools.listChanged=true`.            |
| `tools/list`                   | Supported        | All 36 registered tools are returned with object input schemas.                    |
| `tools/call`                   | Supported        | `model_list` returns structured content plus a JSON text fallback.                 |
| Protocol tool errors           | Supported        | Unknown tool calls raise FastMCP `ToolError` instead of invoking local code.       |
| Studio HTTP auth               | Supported        | `/health` is public; `/runs` and `/tools/{name}` require bearer auth.              |
| HTTP tool policy               | Supported        | Studio tool calls use a fixed allow-list, rate limits, and confirmation gates.     |
| Tool list change notifications | Declared static  | The server advertises list changes, but Fovux has a static release-time registry.  |
| Prompts                        | Empty            | No Fovux prompts are registered in this release.                                   |
| Resources                      | Empty            | No Fovux MCP resources are registered in this release.                             |
| MCP Tasks                      | Unsupported      | Fovux does not advertise `capabilities.tasks`; HTTP background jobs are REST-only. |
| Roots                          | Client-dependent | Fovux does not request `roots/list`; filesystem bounds are local config based.     |
| Sampling                       | Unsupported      | Fovux tools do not call `sampling/createMessage`.                                  |
| Elicitation                    | Unsupported      | Fovux tools do not call `elicitation/create`.                                      |

## Transport Policy

Use stdio for MCP clients:

```json
{
    "mcpServers": {
        "fovux": {
            "command": "fovux-mcp",
            "args": ["serve"]
        }
    }
}
```

Use the HTTP bridge only for Fovux Studio and trusted local automation:

```bash
fovux-mcp serve --http --tcp --host 127.0.0.1 --port 7823
```

The HTTP bridge intentionally exposes REST routes such as `/health`, `/runs`,
`/runs/{run_id}/stream`, and `/tools/{name}`. It does not implement the MCP
Streamable HTTP single endpoint, `MCP-Protocol-Version` header negotiation, or
OAuth resource-server metadata.

## Unsupported Feature Rules

- Do not add client-feature requests for roots, sampling, or elicitation unless
  the tool checks the negotiated client capability first.
- Do not map Studio HTTP background operations to MCP Tasks without adding the
  `tasks` capability and protocol contract tests.
- Do not expose mutating or destructive tools over the HTTP bridge without an
  explicit policy entry, rate limit, and `confirm=true` requirement.
- Keep stdio stdout reserved for JSON-RPC messages. FastMCP banner and update
  checks are disabled in the stdio runner.

## Validation Commands

```bash
cd fovux-mcp
uv run pytest -m contract
uv run fovux-mcp --version
uv run fovux-mcp serve --http --tcp --host 127.0.0.1 --port 7823
```
