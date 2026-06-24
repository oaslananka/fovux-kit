# MCP 2025-06-18 Conformance

This checklist records the Fovux MCP surface for protocol revision `2025-06-18`.
It separates the stdio MCP server from the Fovux Studio local API so MCP clients
do not treat the Studio REST/SSE bridge as Streamable HTTP.

## Source Verification

Checked on 2026-06-24:

- MCP specification `2025-06-18`: transports, lifecycle, tools, and authorization pages at
  `modelcontextprotocol.io`.
- Transport requirements verified against the official Streamable HTTP page: stdio and Streamable
  HTTP are the two standard transports; Streamable HTTP requires one MCP endpoint supporting JSON-RPC
  POST/GET semantics, optional SSE, session headers, and protocol-version headers.
- Installed package: `fastmcp 3.4.2`.

## Conformance Checklist

| Surface                        | Status          | Evidence                                                                            |
| ------------------------------ | --------------- | ----------------------------------------------------------------------------------- |
| Protocol revision              | Targeted        | Fovux tracks MCP `2025-06-18` for current conformance planning.                     |
| stdio transport                | Supported       | `fovux-mcp` with no subcommand starts the FastMCP stdio server.                     |
| Streamable HTTP transport      | Not exposed     | `fovux-mcp serve --http` is the Fovux Studio local API, not an MCP endpoint.        |
| Lifecycle                      | Covered         | The stdio contract test initializes, lists tools, calls a tool, then closes.        |
| Tools capability               | Covered         | Server initialization advertises tool capability through FastMCP.                   |
| `tools/list`                   | Covered         | All 47 registered tools are returned with object input schemas in stdio tests.      |
| `tools/call`                   | Covered         | Contract tests call real tools and assert structured output/error behavior.         |
| Protocol tool errors           | Covered         | Unknown tool calls raise FastMCP `ToolError` instead of invoking local code.        |
| Studio local API auth          | Covered         | `/health` is public; `/runs` and `/tools/{name}` require bearer auth.               |
| Studio local API policy        | Covered         | Tool calls use a fixed allow-list, rate limits, scope checks, and challenge gates.  |
| Tool list change notifications | Declared static | Fovux has a static release-time registry; dynamic list mutation is not supported.   |
| Prompts                        | Empty           | No Fovux prompts are registered in this release.                                    |
| Resources                      | Empty           | No Fovux MCP resources are registered in this release.                              |
| MCP Tasks                      | Unsupported     | Fovux does not advertise `capabilities.tasks`; background jobs are Studio API-only. |
| Roots                          | Client-dependent | Fovux does not request `roots/list`; filesystem bounds are local config based.     |
| Sampling                       | Unsupported     | Fovux tools do not call `sampling/createMessage`.                                   |
| Elicitation                    | Unsupported     | Fovux tools do not call `elicitation/create`.                                       |

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

Use the Studio local API only for Fovux Studio and trusted local automation:

```bash
fovux-mcp serve --http --tcp --host 127.0.0.1 --port 7823
```

The Studio local API intentionally exposes REST routes such as `/health`, `/runs`,
`/runs/{run_id}/stream`, and `/tools/{name}`. It does not implement the MCP
Streamable HTTP single endpoint, `MCP-Protocol-Version` header negotiation, or
OAuth resource-server metadata.

## Streamable HTTP Implementation Requirements

A future official `/mcp` endpoint must not be advertised until tests prove:

- JSON-RPC `initialize`, `tools/list`, and `tools/call` work on one endpoint;
- HTTP POST and GET semantics match MCP Streamable HTTP;
- `Accept`, `Content-Type`, `Mcp-Session-Id`, and `MCP-Protocol-Version` behavior is correct;
- local deployments validate `Origin`, bind to localhost by default, and require authentication;
- existing Studio local API routes remain backwards compatible.

## Unsupported Feature Rules

- Do not add client-feature requests for roots, sampling, or elicitation unless the tool checks the
  negotiated client capability first.
- Do not map Studio local API background operations to MCP Tasks without adding the `tasks`
  capability and protocol contract tests.
- Do not expose mutating or destructive tools over the Studio local API without an explicit policy
  entry, rate limit, and `confirm=true` requirement.
- Keep stdio stdout reserved for JSON-RPC messages. FastMCP banner and update checks are disabled in
  the stdio runner.

## Validation Commands

```bash
cd fovux-mcp
uv run pytest -m contract
uv run fovux-mcp --version
uv run fovux-mcp serve --http --tcp --host 127.0.0.1 --port 7823
```
