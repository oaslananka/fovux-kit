# Fovux 1.6.0 Release Notes

Fovux 1.6.0 is the current release candidate for the local-first edge-AI computer vision
workbench. Publication remains pending only for the changed packages identified below; unchanged
components retain their previously verified release status.

## Package Versions and Release Evidence

<!-- prettier-ignore-start -->
<!-- release-baseline:start -->
| Component | Version | Channel status | Evidence |
| --- | --- | --- | --- |
| Python package `fovux-mcp` | `1.6.0` | Pending publication | Generated after registry verification |
| npm wrapper `fovux-mcp` | `1.6.0` | Pending publication | Generated after registry verification |
| VS Code extension `oaslananka.fovuxstudiokit` | `1.5.0` | Pending publication | Generated after marketplace verification |
<!-- release-baseline:end -->
<!-- prettier-ignore-end -->

The final GitHub Release evidence for changed packages will include:

- PyPI and npm registry verification, package smoke-test results, SBOMs, checksums, and provenance;
- VSIX packaging plus VS Marketplace and Open VSX publication verification;
- registry verification evidence JSON for every package published in this release.

## Included Changes

### Python package `fovux-mcp` 1.6.0

#### Fixes

- Backend fix.

### npm wrapper `fovux-mcp` 1.6.0

#### Chores

- Wrapper sync.

### Fovux Studio 1.5.0

#### Features

- Studio feature.

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
