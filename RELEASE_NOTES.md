# Fovux 1.6.0 Release Notes

Fovux 1.6.0 is the current reviewed release baseline for the local-first edge-AI computer vision
workbench. Package publication has been verified by the release workflow across every configured
registry and extension marketplace.

## Package Versions and Release Evidence

<!-- release-baseline:start -->
| Component | Published version | Channel status | Evidence |
| --- | --- | --- | --- |
| Python package `fovux-mcp` | `1.6.0` | Published on PyPI | `fovux_mcp-1.6.0-py3-none-any.whl`, `fovux_mcp-1.6.0.tar.gz`, `fovux-mcp-sbom.spdx.json`, `fovux-mcp.sha256`, `registry-verification-python.json` |
| npm wrapper `fovux-mcp` | `1.6.0` | Published on npm | `npm registry metadata`, `wrapper CLI smoke result`, `fovux-mcp-npm-v1.6.0 source release`, `registry-verification-npm.json` |
| VS Code extension `oaslananka.fovuxstudiokit` | `1.5.0` | Published on VS Marketplace and Open VSX | `fovuxstudiokit.vsix`, `fovux-studio-sbom.spdx.json`, `fovux-studio.sha256`, `registry-verification-studio.json` |
<!-- release-baseline:end -->

The verified GitHub Release evidence includes:

- VSIX packaging status and publish results for VS Marketplace and Open VSX;
- SPDX SBOM files, checksums, and provenance attestations;
- registry verification evidence JSON and a smoke-test result for every published channel.

## Included Changes

### Python package `fovux-mcp` 1.6.0

#### Features

* **studio:** generate LM tools from backend schemas ([8241d12](https://github.com/oaslananka/fovux-kit/commit/8241d129ed3c6cde6e44ea8075a4c8db02d34881))


#### Bug Fixes

* **release:** constrain baseline update paths ([de44986](https://github.com/oaslananka/fovux-kit/commit/de44986b5e33a22024d1faadda48bc89228a9ad7))
* **release:** derive baseline test versions ([c63b1d2](https://github.com/oaslananka/fovux-kit/commit/c63b1d2bfdb0adbbc9df71aa7a6967c7e58152ee))
* **release:** derive baseline versions from manifests ([01e4a22](https://github.com/oaslananka/fovux-kit/commit/01e4a22245338b27a5ef030b74929e562ccdf57f))
* **release:** enforce release-note containment ([2916a09](https://github.com/oaslananka/fovux-kit/commit/2916a098daf3e61a49c71506c355d6f9d3ed2de9))
* **release:** make candidate notes publication-aware ([a678032](https://github.com/oaslananka/fovux-kit/commit/a67803232b7963c8dce65ad01405e031f13e329e))
* **security:** replace Snyk with OSV Scanner ([#163](https://github.com/oaslananka/fovux-kit/issues/163)) ([85e2397](https://github.com/oaslananka/fovux-kit/commit/85e2397d94345c60c4742388b34e2c6cbc789cc7)), closes [#162](https://github.com/oaslananka/fovux-kit/issues/162)

### npm wrapper `fovux-mcp` 1.6.0

#### Miscellaneous Chores

* **fovux-mcp-npm:** Synchronize fovux-mcp versions

### Fovux Studio 1.5.0

#### Features

* **studio:** generate LM tools from backend schemas ([8241d12](https://github.com/oaslananka/fovux-kit/commit/8241d129ed3c6cde6e44ea8075a4c8db02d34881))

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
