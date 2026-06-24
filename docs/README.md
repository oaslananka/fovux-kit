# Fovux Documentation

This directory holds monorepo-level documentation for operating, releasing, and demonstrating
Fovux. Product documentation for the MCP server lives under `fovux-mcp/docs`.

## Start Here

- [Architecture](architecture.md) explains the MCP server, VS Code extension, Studio local API,
  local auth model, and run lifecycle.
- [Repository Operations](repository-operations.md) describes protected branches, remotes, and release gates.
- [Demo Script](demo-script.md) is the 90-second recording checklist and screenshot set.
- [MCP Docs](../fovux-mcp/docs/index.md) cover tools, configuration, security, and user workflows.
- [Studio Source](../fovux-studio/README.md) covers extension setup, packaging, and UI features.

## Release Readiness

The release-readiness hardening train is designed to keep source, local checks, and CI aligned:

- `oaslananka/fovux-kit` is the canonical public source repository.
- GitHub Actions in this repository run automatic checks on pushes and pull requests.
- Registry publishing is driven by release-please outputs and protected GitHub environments.

Before a release, run the repo-level quality gate:

```bash
task ci
```
