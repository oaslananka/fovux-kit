# Fovux 1.6.1 Release Notes

Fovux 1.6.1 is the current reviewed release baseline for the local-first edge-AI computer vision
workbench. Package publication has been verified by the release workflow across every configured
registry and extension marketplace.

## Package Versions and Release Evidence

<!-- release-baseline:start -->
| Component | Published version | Channel status | Evidence |
| --- | --- | --- | --- |
| Python package `fovux-mcp` | `1.6.1` | Published on PyPI | `fovux_mcp-1.6.1-py3-none-any.whl`, `fovux_mcp-1.6.1.tar.gz`, `fovux-mcp-sbom.spdx.json`, `fovux-mcp.sha256`, `registry-verification-python.json` |
| npm wrapper `fovux-mcp` | `1.6.1` | Published on npm | `npm registry metadata`, `wrapper CLI smoke result`, `fovux-mcp-npm-v1.6.1 source release`, `registry-verification-npm.json` |
| VS Code extension `oaslananka.fovuxstudiokit` | `1.5.1` | Published on VS Marketplace and Open VSX | `fovuxstudiokit.vsix`, `fovux-studio-sbom.spdx.json`, `fovux-studio.sha256`, `registry-verification-studio.json` |
<!-- release-baseline:end -->

The verified GitHub Release evidence includes:

- VSIX packaging status and publish results for VS Marketplace and Open VSX;
- SPDX SBOM files, checksums, and provenance attestations;
- registry verification evidence JSON and a smoke-test result for every published channel.

## Included Changes

### Python package `fovux-mcp` 1.6.1

#### Bug Fixes

* **ci:** reconcile Sonar and Codecov coverage signals ([#180](https://github.com/oaslananka/fovux-kit/issues/180)) ([eb56de7](https://github.com/oaslananka/fovux-kit/commit/eb56de71a3b23969440e81351ef0e67d38dd5994)), refs [#173](https://github.com/oaslananka/fovux-kit/issues/173)
* **mcp:** stabilize raw stdio startup ([#178](https://github.com/oaslananka/fovux-kit/issues/178)) ([f4887ae](https://github.com/oaslananka/fovux-kit/commit/f4887ae2d2ba44e3686ac75aca0c3d6db2ffab76)), closes [#172](https://github.com/oaslananka/fovux-kit/issues/172)

### npm wrapper `fovux-mcp` 1.6.1

#### Miscellaneous Chores

* **fovux-mcp-npm:** Synchronize fovux-mcp versions

### Fovux Studio 1.5.1

#### Bug Fixes

* **ci:** reconcile Sonar and Codecov coverage signals ([#180](https://github.com/oaslananka/fovux-kit/issues/180)) ([eb56de7](https://github.com/oaslananka/fovux-kit/commit/eb56de71a3b23969440e81351ef0e67d38dd5994)), refs [#173](https://github.com/oaslananka/fovux-kit/issues/173)

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
- registry, VS Marketplace, and Open VSX verification in the release workflow
