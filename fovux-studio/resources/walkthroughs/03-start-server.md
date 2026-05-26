# Start the Server

Fovux Studio uses a local HTTP transport to read run state, invoke tools, and stream training metrics. The server binds to `127.0.0.1` and authenticates requests with the token stored in your `FOVUX_HOME`.

## Steps

1. Start the backend with `fovux-mcp serve --http --tcp`.
2. Or run the `Fovux: Start Local Server` command from VS Code.
3. Confirm the server is healthy at `http://127.0.0.1:7823/health`.

## Next Step

Click the button above to move to the next step.
