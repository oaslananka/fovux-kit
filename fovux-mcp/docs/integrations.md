# Integrations

## Cursor and Windsurf

Use the standard MCP server configuration with `command: "fovux-mcp"`. Fovux is designed to be called by an existing coding or assistant workflow rather than acting as its own chat UI.

## VS Code

There are two layers:

- MCP client integration for conversational tool use
- Fovux Studio for local dashboards and inspections

Run the Fovux Studio local API when Studio needs live run metrics:

```bash
fovux-mcp serve --http --host 127.0.0.1 --port 7823
```

## Other MCP Clients

Use Fovux as a standard stdio MCP server entry in any MCP-compatible client and keep the filesystem
local. The `serve --http` command is the Fovux Studio local API/custom REST+SSE bridge, not an MCP Streamable HTTP
endpoint.
