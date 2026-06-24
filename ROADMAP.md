# Roadmap

This document starts from the current published baseline reviewed on 2026-06-24:

- `fovux-mcp` Python package: `1.3.0`
- `fovux-mcp` npm wrapper: `1.3.0`
- `fovux-studio`: `1.2.0`
- Backend tool registry: 47 local tools
- Studio Language Model Tools: 20 granular tools plus 1 generic fallback tool

Themes and dates are targets, not commitments. GitHub milestones are the source of truth for
issue-level scope and progress.


## Release and changelog boundary

- Released work is recorded in [`CHANGELOG.md`](CHANGELOG.md) and package changelogs.
- Planned work is tracked in the milestone sections below and in their linked GitHub issues.
- GitHub Releases must include package versions, VSIX/marketplace status, SBOM/provenance assets,
  checksums, and registry smoke-test evidence before a release is considered verified.

## [v1.3.1 — Stabilization & Documentation Truth](https://github.com/oaslananka/fovux-kit/milestone/1)

**Target:** 2026-07-15

**Theme:** make public documentation, package metadata, CI gates, and registry verification match the
actual 1.3.0 release state.

- Keep README, architecture docs, release notes, package metadata, and MkDocs nav in sync.
- Fail CI on tool documentation, MkDocs navigation, docs code-block, and version drift.
- Improve local bootstrap documentation for `go-task`, `uv`, `pnpm`, `actionlint`, and `gitleaks`.
- Remove Python 3.12+ SQLite datetime and Starlette/httpx deprecation warnings.
- Fix registry smoke verification for PyPI/npm checks.

**DRI:** @oaslananka

## [v1.4.0 — MCP Conformance & Agent Safety](https://github.com/oaslananka/fovux-kit/milestone/2)

**Target:** 2026-08-31

**Theme:** make the MCP contract explicit, testable, and safe for agent-driven workflows.

- Decide whether to implement a standards-compliant Streamable HTTP MCP endpoint or keep the current
  local HTTP/SSE server documented as a Studio API/custom transport.
- Add MCP conformance coverage for initialize, `tools/list`, `tools/call`, pagination, errors, and
  protocol-version handling.
- Add tool schema snapshots and registry-to-docs-to-Studio consistency checks.
- Strengthen policy modes, challenge flow, scope bypass auditing, and approval UX.
- Maintain an MCP client interoperability matrix.

**DRI:** @oaslananka

## [v1.5.0 — Studio Workflow & Dataset Intelligence](https://github.com/oaslananka/fovux-kit/milestone/3)

**Target:** 2026-10-15

**Theme:** turn Fovux Studio into a guided end-to-end workflow for dataset quality, training,
evaluation, and export.

- Build a guided dataset validation → training preflight → training → evaluation → export path.
- Improve duplicate/leakage checks, split policy reporting, and remediation output.
- Require `train_preflight` before `train_start` in guided and agent workflows.
- Harden dashboard streaming, cancellation/resume UX, run comparison, and offline fallback.
- Add VS Code extension e2e smoke tests for Workspace Trust, webviews, commands, and LM tools.

**DRI:** @oaslananka

## [v1.6.0 — Edge Export & Deployment Intelligence](https://github.com/oaslananka/fovux-kit/milestone/4)

**Target:** 2026-11-30

**Theme:** make export and deployment advice target-aware and reproducible.

- Maintain a current export matrix for YOLO, ONNX, TensorRT, CoreML, OpenVINO, TFLite, NCNN, and
  RKNN targets.
- Add deployment profiles for Jetson, Raspberry Pi, Apple Silicon, CPU-only, browser, and industrial
  edge environments.
- Add reproducible latency benchmarks with warmup, percentiles, hardware manifests, and artifact
  comparison.
- Add target-specific INT8 calibration and validation workflow.
- Document licensing boundaries for Apache core and optional third-party integrations.

**DRI:** @oaslananka

## [v2.0.0 — Extensibility, Supply Chain & Ecosystem Readiness](https://github.com/oaslananka/fovux-kit/milestone/5)

**Target:** 2027-03-31

**Theme:** stabilize the extension points, release evidence, and supply-chain posture required for a
larger ecosystem.

- Define plugin, SDK, and public API stability guarantees.
- Move publishing toward trusted publishing, OIDC, provenance, signed attestations, and verification
  docs.
- Update the MCP threat model for tool poisoning, prompt injection, data exfiltration, and remote
  server risks.
- Add contributor ladder, ADR lifecycle, project automation, and issue lifecycle policy.
- Ship VSIX/Open VSX/Marketplace release evidence, package-size gates, and rollback playbooks.

**DRI:** @oaslananka

## [Backlog — Research & Product Discovery](https://github.com/oaslananka/fovux-kit/milestone/6)

- Evaluate MCP Apps / interactive MCP UI direction against the Fovux Studio strategy.

---

To propose a feature, open a GitHub issue or discussion in
[`oaslananka/fovux-kit`](https://github.com/oaslananka/fovux-kit).
