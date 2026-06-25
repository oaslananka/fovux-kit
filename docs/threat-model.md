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
