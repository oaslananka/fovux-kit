# Threat Model

This document describes the trust boundaries and threat surfaces for Fovux
using a STRIDE-inspired framework.

## Trust Boundaries

### FOVUX_HOME
- **Description:** Local directory storing runs, models, configs, and `auth.token`.
- **Trust level:** Fully trusted. Only local processes should have access.
- **Threats:** Unauthorized file access, symlink attacks, path traversal.

### HTTP Transport
- **Description:** FastAPI server on `127.0.0.1:7823`.
- **Trust level:** Authenticated via bearer token. Bound to loopback only.
- **Threats:** Token leakage, localhost bypass (e.g., DNS rebinding).
- **Container note:** The Docker image listens on the container bridge interface so
  published ports work; `docker-compose.yml` binds the host side to `127.0.0.1`.

### Subprocess Training
- **Description:** Ultralytics training runs spawned as child processes.
- **Trust level:** Trusted (runs user-controlled code).
- **Threats:** Resource exhaustion, zombie processes, PID reuse.

### ONNX Deserialization
- **Description:** ONNX model files loaded for export and inference.
- **Trust level:** Semi-trusted (user-provided model files).
- **Threats:** Malicious ONNX proto payloads, path traversal in model metadata.

### Registry Tokens
- **Description:** PyPI, VS Code Marketplace, and Open VSX tokens managed via Doppler.
- **Trust level:** CI-only, never exposed to end users.
- **Threats:** Token leakage in CI logs, misconfigured secrets.

## Non-Goals

- **Network-facing deployment.** Fovux is designed for local use only.
- **Multi-user access control.** Single-user, single-machine assumed.
- **Encrypted storage.** `FOVUX_HOME` is not encrypted at rest.

## Mitigations

| Threat | Mitigation |
|---|---|
| Path traversal in tool inputs | All file paths validated against `FOVUX_HOME` and allowed roots |
| Token leakage | Bearer token stored with restrictive file permissions; rotatable via `fovux-mcp rotate-token` |
| DNS rebinding | HTTP server binds to `127.0.0.1` by default and does not bind to all interfaces unless explicitly configured |
| Zombie processes | Training worker writes PID and status atomically; `train_stop` uses process group kill |
| Malicious ONNX | Only user-provided local models are loaded; no remote model download |
| CI token exposure | Doppler secrets injected at runtime; never committed or logged |
