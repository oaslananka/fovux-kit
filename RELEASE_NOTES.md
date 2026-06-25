# Fovux 1.4.0 Release Notes

Fovux 1.4.0 is the current reviewed release baseline for the local-first edge-AI computer vision
workbench. It consolidates the expanded MCP tool registry, active-learning queue workflow, policy and
audit tools, support/reproducibility bundles, and Studio guarded-tool UX.


## Package Versions and Release Evidence

| Release item | Current status | Required GitHub Release evidence |
| ------------ | -------------- | -------------------------------- |
| Python package | `fovux-mcp` `1.4.0` published on PyPI | Wheel, sdist, SHA256 checksums, SPDX SBOM, provenance attestation, and PyPI registry smoke result |
| npm wrapper | `fovux-mcp` `1.4.0` published on npm | npm provenance, package metadata check, wrapper CLI smoke result, and registry verification evidence JSON |
| VS Code extension | `oaslananka.fovuxstudiokit` `1.3.0` published on VS Marketplace and Open VSX | VSIX artifact/status, package-size check, marketplace verification, Open VSX verification, SBOM, checksums, and provenance attestation |

GitHub release notes for every future release must explicitly include:

- package versions for `fovux-mcp`, the npm wrapper, and `fovux-studio`;
- VSIX packaging, VS Marketplace, and Open VSX status;
- SBOM, checksum, and provenance/attestation asset names or links;
- registry verification evidence and smoke-test result for each published channel;
- known limitations or skipped channels, including the reason and follow-up issue.

## Headline Wins

- **47 local backend tools.** The backend registry now covers dataset inspection, validation,
  active learning, training, evaluation, export, quantization, inference, benchmarking, run
  management, policy/audit, and support-bundle workflows.
- **Active Learning Queue.** Queue ranking, listing, and submission tools support review-driven data
  improvement loops.
- **Policy and Audit Surface.** Policy status, policy mode changes, audit event listing, support
  bundles, and reproducibility bundles make agent actions easier to inspect.
- **Studio Tooling Growth.** Fovux Studio exposes 20 granular Language Model Tools plus one generic
  fallback tool for hosts that support VS Code LM tools.
- **Local-first Transport Clarity.** MCP stdio remains the standards-oriented agent surface; the
  HTTP/SSE server is documented as a local Studio API/custom bridge until Streamable HTTP conformance
  is implemented.
- **Documentation Gates.** Tool docs, MkDocs navigation, docs code-block lint, and version/tool-count
  truth checks are part of the release-quality path.

## Upgrade Path

```bash
# Backend
uv tool upgrade fovux-mcp

# npm wrapper
npm install -g fovux-mcp@latest

# Source checkout
cd fovux-kit/fovux-mcp
uv sync --frozen --extra dev
```

## Release Validation

- `python scripts/check_versions.py`
- `python scripts/check_docs_truth.py`
- `cd fovux-mcp && uv run python scripts/check_tool_docs.py`
- `cd fovux-mcp && uv run mkdocs build --strict`
- `python scripts/lint_docs_code.py .`
