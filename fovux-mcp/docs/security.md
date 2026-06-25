# Security Model

Fovux keeps `stdio` as the MCP transport and treats the Fovux Studio local API as a local, authenticated control plane.

## Studio local API auth

- `GET /health` is the only unauthenticated endpoint.
- All other Studio local API routes require `Authorization: Bearer <token>`.
- If an `Origin` header is present, it must be a trusted VS Code webview, VS Code CDN, or localhost origin; otherwise the request is rejected with `403 Forbidden` before tool execution.
- The bearer token is stored at `FOVUX_HOME/auth.token`.
- On Unix-like systems the token file is created with restrictive permissions when possible.


## Local bind and remote mode

The Studio local API is designed for same-machine use. The CLI refuses non-local bind hosts unless
`--allow-nonlocal-bind` is supplied explicitly. That flag is an operational escape hatch, not a
remote-server security model.

A remote or multi-user Fovux server must not rely on the local bearer token alone. Before remote mode
can be supported, it needs a separate OAuth/OIDC resource-server design with TLS termination, audience
binding, scoped access tokens, token revocation, protected resource metadata, audit correlation, and
reverse-proxy/network ACL guidance.

## Token lifecycle

Generate the current token by starting the HTTP server once:

```bash
fovux-mcp serve --http
```

Rotate the token explicitly. The raw token is hidden by default; use the fingerprint and token file path for logs and support bundles:

```bash
fovux-mcp rotate-token
```

For one-time manual local client configuration, reveal the raw token explicitly:

```bash
fovux-mcp rotate-token --show-token
```

The VS Code extension reads the token from the same `FOVUX_HOME` directory, so `fovux.home` in Studio and `FOVUX_HOME` for `fovux-mcp` must point at the same location.


## Policy mode matrix

Agent-facing Studio local API calls use a formal policy matrix exposed by `get_policy_status`:

| Mode | Intended environment | Scope checks | Confirmation behavior | Audit level |
| ---- | -------------------- | ------------ | --------------------- | ----------- |
| `safe` | Interactive local review | Enforced | Required for mutating, long-running, and high-impact categories | strict |
| `developer` | Default single-user local development | Enforced | Per-tool policy | standard |
| `automation` | Trusted local automation with scoped tokens | Enforced | Bypassed for trusted automation | elevated |
| `lab` | Isolated lab/test fixtures only | Bypassed | Bypassed | bypass |

`lab` is the only mode that bypasses scope checks. Every lab bypass writes a `policy_scope_bypass`
audit event containing the required scope, provided scopes, category, and bypass status.

## Challenge prompts

Tools that require confirmation return challenge prompts with `tool_name`, `risk_level`, `input_paths`,
`output_paths`, `resolved_paths`, `destructive_impact`, `irreversible_effects`, and `human_prompt`. Studio must display these
fields before it sends the returned `challenge_id` back to `/tools/{name}`.

## HTTP tool policy

The Studio local API exposes a fixed allow-list with per-tool timeouts and concurrency limits. Filesystem-writing, mutating, long-running, or destructive tools require a trusted local UI confirmation field (`confirm=true`) before execution. Audit logs record token fingerprints, origin, tool name, redacted argument hashes, status, duration, and failure class without storing raw bearer tokens or full payloads.

## Rate limiting

`POST /tools/*` is rate-limited per client IP to reduce accidental hammering from local scripts or misconfigured clients. Exceeded requests return `429 Too Many Requests` with `Retry-After`.

## Filesystem safety

Fovux validates writable output paths before creating artifacts. By default, writes are constrained to:

- `FOVUX_HOME`
- the current working directory
- any explicitly allowed roots

HTTP mode is stricter than stdio mode and is intended for same-machine Studio workflows.

## Dataset YAML validation

Training inputs are validated before the detached worker starts:

- unsafe YAML loaders are not used
- only known dataset keys are accepted
- normalized dataset paths must resolve under the dataset root

## Supply chain

The GitHub Actions release train produces SBOM artifacts and keeps Python and Studio builds on a
single CI system. Publishing remains manual-gated by the maintainer.
