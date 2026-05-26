# Security Policy

## Supported Versions

| Version | Supported            |
| ------- | -------------------- |
| 4.x     | Active               |
| < 4.0   | No longer maintained |

## Security Model

Fovux is a **local-first tool**. The fovux-mcp HTTP transport binds exclusively to
`127.0.0.1` (localhost) and is never exposed to a network interface by default.

The detailed threat model is maintained in [docs/threat-model.md](docs/threat-model.md). Keep that
document in sync when changing transport auth, local file access, command spawning, or release
signing behavior.

### Authentication

- The HTTP transport is protected by a 32-byte hex bearer token stored at
  `$FOVUX_HOME/auth.token` with mode `0600`.
- The token is generated on first startup using `secrets.token_hex(32)`.
- Rotate the token at any time:

  ```bash
  fovux-mcp rotate-token
  ```

- The default rotation output prints the token path and fingerprint only. Use
  `fovux-mcp rotate-token --show-token` only for one-time local client setup.
- After rotation, restart any MCP clients or restart the VS Code extension
  to reload the new token.

Token rotation procedure:

1. Stop active Studio dashboards or MCP clients that are using the old token.
2. Run `fovux-mcp rotate-token`.
3. Restart `fovux-mcp serve --http` if the server was already running.
4. Reload the VS Code window or run `Fovux: Refresh Views` so Studio reads the new token from
   `$FOVUX_HOME/auth.token`.
5. If a token was exposed in logs or a support bundle, delete that bundle and rotate again after
   confirming all clients are disconnected.

### Rate Limiting

The HTTP transport enforces a sliding-window rate limit of **100 POST requests per
60 seconds per client IP**. Since the server binds to localhost only, this limit
applies per local process.

### HTTP Tool Policy

HTTP tool calls use an explicit allow-list with per-tool timeouts, concurrency limits, and audit
events. Mutating, filesystem-writing, long-running, and destructive tools require `confirm=true`
from a trusted local UI action. Audit events include token fingerprints and argument hashes only;
raw bearer tokens and full tool payloads are not logged.

### Reverse-Proxy Warning

Do **not** place fovux-mcp behind a reverse proxy that forwards requests from
untrusted networks. The rate-limiter keys on `request.client.host`; behind a
reverse proxy all clients collapse to the proxy IP and rate limiting becomes
ineffective.

### CORS

The CORS allow-list is restricted to `vscode-webview://` origins and
`*.vscode-cdn.net`. No external origins are permitted.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Email: **oaslananka@gmail.com**

Include:

1. A description of the vulnerability and its potential impact
2. Reproduction steps (version, OS, configuration)
3. Any relevant logs (redact tokens and paths)

You can expect an acknowledgement within **72 hours** and a status update within
**7 days**.

Patches are released as patch versions (e.g. `2.0.1`) and announced in the
[CHANGELOG](CHANGELOG.md) with a `Security` section.
