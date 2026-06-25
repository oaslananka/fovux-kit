# Threat Model

This document describes the trust boundaries and threat surfaces for Fovux
using a STRIDE-inspired framework.

## Trust Boundaries

### FOVUX_HOME

- **Description:** Local directory storing runs, models, configs, and `auth.token`.
- **Trust level:** Fully trusted. Only local processes should have access.
- **Threats:** Unauthorized file access, symlink attacks, path traversal.

### Fovux Studio Local API

- **Description:** FastAPI custom REST/SSE server on `127.0.0.1:7823` or a Unix socket.
- **Trust level:** Same-machine only; authenticated via local bearer token and scoped session tokens.
- **Threats:** Token leakage, localhost bypass, DNS rebinding, accidental non-local bind exposure.
- **Controls:** All non-health routes require auth, browser requests with untrusted `Origin` are rejected, and non-local bind hosts require explicit `--allow-nonlocal-bind`.
- **Container note:** The Docker image listens on the container bridge interface so published ports work; `docker-compose.yml` binds the host side to `127.0.0.1`.

### Subprocess Training

- **Description:** Ultralytics training runs spawned as child processes.
- **Trust level:** Trusted (runs user-controlled code).
- **Threats:** Resource exhaustion, zombie processes, PID reuse.

### ONNX Deserialization

- **Description:** ONNX model files loaded for export and inference.
- **Trust level:** Semi-trusted (user-provided model files).
- **Threats:** Malicious ONNX proto payloads, path traversal in model metadata.

### Registry Tokens

- **Description:** PyPI, VS Code Marketplace, and Open VSX tokens stored as protected GitHub Actions secrets.
- **Trust level:** CI-only, never exposed to end users.
- **Threats:** Token leakage in CI logs, misconfigured secrets.

## Non-Goals

- **Network-facing deployment with local bearer auth.** Fovux is designed for local use only.
- **Multi-user access control without OAuth/OIDC.** Single-user, single-machine is assumed until a separate remote-server authorization design exists.
- **Encrypted storage.** `FOVUX_HOME` is not encrypted at rest.

## Mitigations

| Threat                        | Mitigation                                                                                                   |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Path traversal in tool inputs | All file paths validated against `FOVUX_HOME` and allowed roots                                              |
| Token leakage                 | Bearer token stored with restrictive file permissions; rotatable via `fovux-mcp rotate-token`                |
| DNS rebinding                 | Studio local API binds locally by default and rejects untrusted browser `Origin` headers before auth/tool execution |
| Accidental remote exposure     | Non-local bind hosts require `--allow-nonlocal-bind`; remote mode still requires a future OAuth/OIDC resource-server design |
| Zombie processes              | Training worker writes PID and status atomically; `train_stop` uses process group kill                       |
| Malicious ONNX                | Only user-provided local models are loaded; no remote model download                                         |
| CI token exposure             | Protected GitHub Actions secrets injected only into publishing jobs; never committed or logged               |

## MCP-specific Agentic Threats

### Tool poisoning and lookalike tools

- **Attack tree:** malicious server advertises a familiar tool name; metadata hides destructive behavior; agent selects the wrong tool; local files or runs are changed.
- **Assumptions:** tool descriptions, annotations, and titles are untrusted unless the server is a trusted local Fovux server.
- **Controls:** canonical tool registry, schema snapshots, Studio LM mapping checks, human confirmation for risky tools, audit events, and scoped HTTP policy.

### Prompt injection through tool output

- **Attack tree:** dataset/model metadata or third-party output contains instructions; agent treats output as authority; agent calls write/export/delete tools.
- **Controls:** tool outputs are data, not instructions; destructive actions require confirmation; Studio shows explicit confirmation messages; policy mode can block risky operations.

### Sensitive data leakage through paths, bundles, or exports

- **Attack tree:** attacker asks for broad support bundle, path traversal, or export to sensitive directory.
- **Controls:** path validation, allowed roots, support bundle redaction, no hosted uploads by default, no telemetry by default, and explicit third-party opt-in.

### Confused-deputy remote MCP exposure

- **Attack tree:** local MCP/HTTP server is bound beyond localhost; browser or remote client reuses token/session; agent grants unintended write scope.
- **Controls:** localhost binding by default, origin checks, bearer/session token auth, non-local bind flag, future OAuth/OIDC resource-server design before remote mode.

## MCP tool security review checklist

Every new MCP tool must answer:

1. What scope does it need: read-only, dataset write, training, export, network, or destructive?
2. Can it read outside `FOVUX_HOME` or workspace roots?
3. Does it accept output paths, and are they validated?
4. Does it need human confirmation or a challenge flow?
5. Does it write audit events with redacted arguments?
6. Are tool name, input schema, output schema, and Studio LM mapping snapshot-tested?
7. Can untrusted tool output cause follow-up actions without user review?
8. Does it preserve local-first and no-telemetry defaults?
