# Changelog

All notable changes to `fovux-studio` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [4.1.8](https://github.com/oaslananka-lab/fovux/compare/fovux-studio-v4.1.7...fovux-studio-v4.1.8) (2026-05-10)


### Miscellaneous Chores

* **fovux-studio:** Synchronize fovux versions

## [4.1.7](https://github.com/oaslananka-lab/fovux/compare/fovux-studio-v4.1.6...fovux-studio-v4.1.7) (2026-05-09)


### Bug Fixes

* **release:** document package distribution pipeline ([#20](https://github.com/oaslananka-lab/fovux/issues/20)) ([36e6d84](https://github.com/oaslananka-lab/fovux/commit/36e6d848b93a5d45aa3ff67e89f14c8f25b9b1c6))

## [4.1.6](https://github.com/oaslananka-lab/fovux/compare/fovux-studio-v4.1.5...fovux-studio-v4.1.6) (2026-05-09)


### Bug Fixes

* **process:** harden resumed worker termination ([a9c692f](https://github.com/oaslananka-lab/fovux/commit/a9c692fa16d69d4d8c23b99c384c0021201799fe))
* **security:** address review hardening follow-ups ([825cd40](https://github.com/oaslananka-lab/fovux/commit/825cd400b2216aa878030446d23ca186e55deb82))
* **security:** harden runtime control surface ([d443d48](https://github.com/oaslananka-lab/fovux/commit/d443d483effc4697c982158854aef7a5d9f7169f))

## [4.1.5](https://github.com/oaslananka-lab/fovux/compare/fovux-studio-v4.1.4...fovux-studio-v4.1.5) (2026-05-08)


### Bug Fixes

* **readme:** update screenshot links to use absolute URLs ([a163ed2](https://github.com/oaslananka-lab/fovux/commit/a163ed2c32ab9a77f5a299ef0ee461fa3a3069c0))
* resolve ruff and eslint errors failing the CI ([edfd82b](https://github.com/oaslananka-lab/fovux/commit/edfd82b4fb4da324a316e49e47a982e8aebc6da7))
* **security:** remove vulnerable uuid transitive lock ([4dc9647](https://github.com/oaslananka-lab/fovux/commit/4dc96473dc994f91eaed578ec4841d3268a8da73))

## [4.1.4] - 2026-04-29

### Changed

- Republished the VSIX with the current README screenshot URLs for Marketplace/Open VSX rendering.

## [4.1.3] - 2026-04-29

### Security

- Pin every GitHub Actions dependency used by Studio CI/release checks to immutable SHAs.
- Keep Scorecard as a published advisory signal without creating code-scanning policy noise.

## [4.1.2] - 2026-04-29

### Changed

- CI now installs pinned `pnpm@10.33.0` through npm instead of Corepack activation to avoid
  Windows runner hangs and keep Node 22/24 matrix builds deterministic.

## [4.1.1] - 2026-04-28

### Added

- CodeLens actions for YOLO `data.yaml` files.
- Run folder file decorations for completed, failed, running, and stopped runs.
- Active-run and session-scoped profile status bar controls.
- Dataset Inspector panels for missing-label images, bounding-box size buckets, and optional
  evaluation-backed confusion matrices.
- Training Launcher preset import-from-run plus JSON import/export.
- TensorRT GPU target grouping in the Export Wizard with CUDA-aware disabling.

### Changed

- Webview metric subscriptions prefer `/stream`, fall back to `/metrics`, and finally fall back to
  polling.
- Annotation Editor state now uses a reducer with draw, select, move, resize, delete, undo, clear,
  and save operations.
- ESLint 9 flat config is now explicit and package builds use deterministic bundle-size gates.

### Security

- Workspace trust is declared as limited and untrusted workspaces cannot start the server or launch
  training.

## [4.1.0] - 2026-04-27

### Added

- 12 granular Language Model Tool registrations for Copilot agent mode and LLM hosts.
- Cross-package compatibility enforcement with `FOVUX_COMPAT` version range checks.
- First-run walkthrough (Getting Started) covering install, profile, server, doctor, dashboard, dataset.
- System Health (Doctor) sidebar with live diagnostics tree view.
- Privacy badge status bar item showing local-only operation.
- `fovux.installBackend` and `fovux.runDoctor` commands for walkthrough steps.
- VSIX bundle-size regression check in CI.

### Changed

- Version unified to `4.1.0` across the monorepo.
- LM tool catalog surfaces granular tools first; generic dispatcher kept as fallback.
- Status bar shows compatibility state (recommended, supported, incompatible).

## [3.0.0] - 2026-04-27

### Added

- resilient SSE reconnect and multiline SSE parsing tests
- Training Launcher run-name preflight, force overwrite, max-concurrency control, and user presets backed by `globalState`
- run timeline and annotation editor webviews
- export recommendations from benchmark latency and model size
- embedded MCP client scaffold and VS Code Language Model Tool registration with user confirmation
- multi-`FOVUX_HOME` profile settings

### Changed

- refresh command now updates runs, models, and exports
- extension HTTP client retries once on 401 after rereading `auth.token`
- dataset preview boxes now render through a reusable canvas layer
- server startup errors now prioritize spawn failures over timeout text

### Security

- webview CSP remains centralized and covered by tests
- Marketplace package build now includes the new timeline and annotation editor bundles

## [2.0.0] - 2026-04-22

### Added

- Training Launcher webview for starting `train_start` runs from VS Code
- Exports tree view backed by `FOVUX_HOME/exports.jsonl`
- run context actions for stop, resume, delete, tag, copy ID, and reveal
- authenticated webview requests using the shared `FOVUX_HOME/auth.token`

### Changed

- activation now uses `onView:*` plus `onStartupFinished`
- extension-host HTTP client no longer owns long-lived metric streams
- webview bundles include a dedicated training launcher entrypoint

### Security

- Studio sends bearer auth headers to every protected Fovux HTTP endpoint
- publishing remains manual-gated through Azure DevOps release variables

## [1.0.0] - 2026-04-21

### Added

- script-enabled React webviews for dashboard, dataset inspector, export wizard, and run comparison
- browser-side HTTP/SSE client helpers for the local Studio transport
- vitest smoke tests for extension activation, command registration, webview HTML bootstrapping, and run tree discovery
- multi-entry `tsup` build producing `out/webviews/*/main.js`

### Changed

- command handlers now open real webviews instead of placeholder HTML
- `pnpm test` now runs Vitest
- ESLint configuration now supports TSX sources and test files

### Fixed

- compare-runs command no longer falls back to an informational toast
- packaged webview entry paths now match the expected `main.js` layout
