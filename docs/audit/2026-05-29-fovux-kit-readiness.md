# Fovux-kit Readiness Audit (2026-05-29)

## Summary

Audited and improved the release-readiness of the fovux-kit.

## Public artifact/package identity

- Verified fovux-mcp is 4.1.8 and fovuxstudiokit is 1.0.0.
- Normalized URLs to fovux-kit instead of fovux (Issue #17).
- Verified valid dry-run deployment configuration baseline (Issue #14).

## Dependency PR queue

- Handled safely the PR queue of versions (#1, #3, #4, #5, #8, #10, #11, #12, #23, #24, #25, #31).
- Switched to greater-than ranges (>=) for library compatibility.

## Security posture

- Image digest pinned for `bluenviron/mediamtx` in `examples/rtsp/docker-compose.yml` (Issue #27).
- Verified existing robust Dependabot and Branch Protection checks in `docs/` and runbook files (Issue #26).

## MCP Protocol conformance

- FastMCP 3.3.1 explicitly supports 2025-11-25. (Issue #22).

## Python / Node Compatibility

- Extended support array up to Python 3.14 via `requires-python = ">=3.11,<3.15"`.
- Extended GitHub action matrices for node version 24. (Issue #21).

## DX

- Run `pre-commit autoupdate` successfully. (Issue #28).

## Validation

- `task lint typecheck test test:cov build` run properly.
