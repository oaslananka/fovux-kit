# Fovux 1.6.2 Release Notes

Fovux 1.6.2 is the current reviewed release baseline for the local-first edge-AI computer vision
workbench. Publication has been verified by the release workflow for every changed package; unchanged
components retain their previously verified release status.

## Package Versions and Release Evidence

<!-- prettier-ignore-start -->
<!-- release-baseline:start -->
| Component | Published version | Channel status | Evidence |
| --- | --- | --- | --- |
| Python package `fovux-mcp` | `1.6.2` | Published on PyPI | `fovux_mcp-1.6.2-py3-none-any.whl`, `fovux_mcp-1.6.2.tar.gz`, `fovux-mcp-sbom.spdx.json`, `fovux-mcp.sha256`, `registry-verification-python.json` |
| npm wrapper `fovux-mcp` | `1.6.2` | Published on npm | `npm registry metadata`, `wrapper CLI smoke result`, `fovux-mcp-npm-v1.6.2 source release`, `registry-verification-npm.json` |
| VS Code extension `oaslananka.fovuxstudiokit` | `1.5.1` | Published on VS Marketplace and Open VSX | `fovuxstudiokit.vsix`, `fovux-studio-sbom.spdx.json`, `fovux-studio.sha256`, `registry-verification-studio.json` |
<!-- release-baseline:end -->
<!-- prettier-ignore-end -->

The verified GitHub Release evidence includes:

- PyPI and npm registry verification, package smoke-test results, SBOMs, checksums, and provenance;
- the existing Studio VSIX packaging, VS Marketplace, and Open VSX evidence remains verified and is not republished;
- registry verification evidence JSON for every package published in this release.

## Included Changes

### Python package `fovux-mcp` 1.6.2

#### Bug Fixes

- **compat:** restore Starlette httpx2 test backend ([#187](https://github.com/oaslananka/fovux-kit/issues/187)) ([54cee72](https://github.com/oaslananka/fovux-kit/commit/54cee72911fee300136747d101a16c9b729fcf96)), closes [#91](https://github.com/oaslananka/fovux-kit/issues/91)

### npm wrapper `fovux-mcp` 1.6.2

#### Miscellaneous Chores

- **fovux-mcp-npm:** Synchronize fovux-mcp versions

## Upgrade Path

```bash
uv tool upgrade fovux-mcp
npm install -g fovux-mcp@latest
```

## Release Validation

- `python scripts/check_versions.py`
- `python scripts/check_docs_truth.py`
- `python scripts/check_release_truth.py`
- `node scripts/validate_release_automation.mjs`
- registry and marketplace verification for packages published by the release workflow
