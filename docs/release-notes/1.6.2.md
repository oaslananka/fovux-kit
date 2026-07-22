# Fovux 1.6.2 Release Notes

Fovux 1.6.2 is the current release candidate for the local-first edge-AI computer vision
workbench. Publication remains pending only for the changed packages identified below; unchanged
components retain their previously verified release status.

## Package Versions and Release Evidence

<!-- prettier-ignore-start -->
<!-- release-baseline:start -->
| Component | Version | Channel status | Evidence |
| --- | --- | --- | --- |
| Python package `fovux-mcp` | `1.6.2` | Pending publication | Generated after registry verification |
| npm wrapper `fovux-mcp` | `1.6.2` | Pending publication | Generated after registry verification |
| VS Code extension `oaslananka.fovuxstudiokit` | `1.5.1` | Published on VS Marketplace and Open VSX | `fovuxstudiokit.vsix`, `fovux-studio-sbom.spdx.json`, `fovux-studio.sha256`, `registry-verification-studio.json` |
<!-- release-baseline:end -->
<!-- prettier-ignore-end -->

The final GitHub Release evidence for changed packages will include:

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
