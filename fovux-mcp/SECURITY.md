# Security Policy

## Supported Versions

| Version | Supported |
| ------- | --------- |
| 1.x     | ✅        |
| < 1.0   | ❌        |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Report vulnerabilities via GitHub's private vulnerability reporting:
[Security Advisories](https://github.com/oaslananka/fovux/security/advisories/new)

Or email the maintainers with subject `[SECURITY] fovux`.

We aim to:

- Acknowledge within 48 hours
- Provide a fix or mitigation within 90 days
- Credit reporters in the release notes (unless anonymity requested)

## Scope

In scope:

- Remote code execution via MCP tool inputs
- Path traversal vulnerabilities
- Subprocess injection
- Insecure deserialization of ONNX/checkpoint files

Out of scope:

- Vulnerabilities in Ultralytics, ONNX Runtime, or other dependencies (report to them)
- Social engineering attacks

## Security design notes

- Fovux runs entirely locally; no data leaves the machine by default
- Subprocess training uses `subprocess.Popen` with explicit argument lists (no `shell=True`)
- All file paths are resolved through `pathlib.Path` and validated before use
- The optional HTTP transport binds to `127.0.0.1` only by default
