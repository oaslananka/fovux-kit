# Changelog

All notable changes to Fovux are documented in this file.

The format follows Keep a Changelog, and this project uses semantic versioning.

## [4.1.4] - 2026-04-29

### Changed

- Republish Fovux Studio with the current Marketplace README screenshot URLs pointing at the
  tracked `fovux-studio/resources/screenshots/` assets on `main`.

## [4.1.3] - 2026-04-29

### Security

- Pin GitHub Actions dependencies and the Python runtime container base image to immutable commit
  and digest references for a fully reproducible supply-chain surface.
- Move Scorecard results out of code-scanning SARIF so policy/advisory checks no longer mask the
  actionable CodeQL and Trivy vulnerability queues.
- Revalidated the authoritative repository after hardening: Dependabot, CodeQL, Trivy, and code
  scanning open alerts are clean.

## [4.1.2] - 2026-04-29

### Fixed

- Avoid recursive filesystem-root scans during dataset format auto-detection, preventing adversarial
  `dataset_inspect("/")` inputs from traversing an entire drive.
- Replace GitHub Actions Corepack pnpm activation with pinned `pnpm@10.33.0` provisioning to
  remove Windows runner hangs while keeping CI installs deterministic.

### Security

- Revalidated the release image/security surface after the root-scan fix: Dependabot, Trivy, and
  CodeQL actionable alerts are clean for the authoritative repository.

## [4.1.1] - 2026-04-28

### Added

- Canonical `/runs/{id}/stream` SSE metric endpoint with `/runs/{id}/metrics` kept as a
  compatibility alias.
- Fovux Studio CodeLens actions for YOLO `data.yaml` files.
- Run folder file decorations for completed, failed, running, and stopped runs.
- Active-run and profile status bar items with session-scoped profile switching.
- Dataset Inspector missing-label and bbox-size panels, plus optional evaluation-backed confusion
  matrix rendering.
- Training Launcher user preset JSON import/export and import-from-run support.
- Export Wizard GPU target grouping with TensorRT visibility and CUDA-aware disabling.
- Reducer-driven Annotation Editor support for draw, select, move, resize, delete, undo, clear, and
  YOLO label save.
- Dependabot minor/patch auto-merge workflow guarded to Dependabot PRs in the org repository.
- SPDX JSON SBOM generation and release artifact upload.

### Changed

- Studio now supports Node.js >= 22 while release builds remain pinned to `.nvmrc` (`24.14.1`).
- CI installs are deterministic: frozen pnpm installs, explicit pnpm 10.33.0, non-suppressed
  yamllint, and current action majors.
- Python coverage threshold is raised to 92% with previously omitted export, eval, benchmark, and
  HTTP route modules covered by focused tests.
- `fovux-mcp` and `fovux` CLI aliases are documented as intentional entry points.
- Release verification now treats `[Unreleased]` as a release-cut blocker rather than a PR blocker.

### Fixed

- Removed the fragile `pnpm.overrides.uuid` override while keeping the lockfile frozen-compatible.
- Added missing contributed Studio commands for walkthrough actions and dataset validation.
- Removed the invalid `enablement: "false"` manifest entry from `fovux.revealPath`.
- Backend install walkthrough action now uses `uv tool install fovux-mcp` as the supported path.
- `nightly-compat.yml` now uses setup-uv and writes a compatibility report consumed by issue
  creation on failure.
- `verify_doppler_secrets.sh` now fails early with a clear message when the Doppler CLI is missing.

### Security

- Workspace trust is declared as limited; server startup and training launch are blocked in
  untrusted workspaces.
- Local metric streams preserve bearer-token auth and rate behavior.
- The `fovux-mcp` container image no longer installs GUI OpenGL/Mesa packages and the Trivy
  workflow now fails on actionable fixed CRITICAL/HIGH findings while ignoring upstream-unfixed
  Debian CVEs that have no patched package available.

## [4.1.0] - 2026-04-27

### Added

- Cross-package compatibility contract enforced at runtime in fovux-studio against fovux-mcp.
- 12 granular Language Model Tools registered by fovux-studio.
- First-run walkthrough covering install, profile, server, doctor, dashboard, and dataset.
- System Health (Doctor) sidebar and privacy badge in fovux-studio.
- MCP Registry manifest, Smithery manifest, and discovery badges.
- JSON Schema export for every MCP tool input.
- Real fovux-mcp server integration tests in CI.
- Sigstore signing and SLSA provenance for release artifacts.
- mkdocs GitHub Pages deploy workflow.
- macOS and Windows backend CI matrix.
- Nightly latest-dependency compatibility job.
- Fuzzing and explicit path-traversal tests for tool inputs.
- ROADMAP, SUPPORT, GOVERNANCE, MAINTAINERS, CITATION.cff, threat-model, release-process, api-stability, troubleshooting docs.
- Canonical label schema, stale/lock workflows, VSIX bundle-size regression check.

### Changed

- All packages share a single source-of-truth version (4.1.0). A pre-commit and CI guard enforces consistency.
- fovux-studio language model tool catalog: granular tools first, generic dispatcher kept as fallback.

### Fixed

- Removed accidentally tracked build artifacts (htmlcov, coverage.xml, junit.xml).
- Eliminated version drift (2.0.0 / 3.0.0 / 4.0.0) across the monorepo.

### Security

- Wheels are signed via Sigstore and carry SLSA Level 3 provenance.
- LLM-driven tool inputs covered by Hypothesis fuzzing and explicit traversal tests.

## [2.0.0] - 2026-04-25

### Added

- Local-first authenticated HTTP transport for Studio and MCP-adjacent workflows.
- Fovux Studio webviews for dashboards, dataset inspection, training launch, run comparison, and export.
- New MCP tools for doctor diagnostics, model profiling, batch inference, and annotation quality checks.
- Structured logging, audit-friendly errors, richer run metadata, and source-first release automation.

### Changed

- Device defaults now prefer automatic accelerator selection instead of forcing CPU.
- Training writes structured metrics for live dashboards and deterministic run status.
- GitHub org CI validates backend, docs, Studio, and release artifacts.

### Fixed

- ONNX export parity now reports failures instead of silently passing runtime errors.
- Dataset validation, conversion, RTSP reconnect, run registry, and Studio webview startup paths were hardened.
- Dependabot-reported `pip` and `uuid` advisories were removed from locked dependency graphs.

### Security

- HTTP endpoints except `/health` require a local bearer token.
- Tool calls are rate-limited.
- Registry publication remains maintainer-gated.
