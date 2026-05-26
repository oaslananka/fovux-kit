# Changelog

All notable changes to `fovux-mcp` are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/).

## [4.1.8](https://github.com/oaslananka-lab/fovux/compare/fovux-mcp-v4.1.7...fovux-mcp-v4.1.8) (2026-05-10)


### Bug Fixes

* **ci:** repair maintenance workflow checks ([#22](https://github.com/oaslananka-lab/fovux/issues/22)) ([8498bfd](https://github.com/oaslananka-lab/fovux/commit/8498bfde26ac88f1ecf92a89ca62bd39f56412c9))

## [4.1.7](https://github.com/oaslananka-lab/fovux/compare/fovux-mcp-v4.1.6...fovux-mcp-v4.1.7) (2026-05-09)


### Bug Fixes

* **release:** document package distribution pipeline ([#20](https://github.com/oaslananka-lab/fovux/issues/20)) ([36e6d84](https://github.com/oaslananka-lab/fovux/commit/36e6d848b93a5d45aa3ff67e89f14c8f25b9b1c6))

## [4.1.6](https://github.com/oaslananka-lab/fovux/compare/fovux-mcp-v4.1.5...fovux-mcp-v4.1.6) (2026-05-09)


### Bug Fixes

* **dataset:** canonicalize image scan roots ([1dee570](https://github.com/oaslananka-lab/fovux/commit/1dee570a68a54f4e53db9544881499278ad01ae3))
* **process:** harden resumed worker termination ([a9c692f](https://github.com/oaslananka-lab/fovux/commit/a9c692fa16d69d4d8c23b99c384c0021201799fe))
* **process:** preserve empty procfs command arguments ([3640024](https://github.com/oaslananka-lab/fovux/commit/3640024cd5dd2d2ad149fb208a6bfca19edaa389))
* **security:** address review hardening follow-ups ([825cd40](https://github.com/oaslananka-lab/fovux/commit/825cd400b2216aa878030446d23ca186e55deb82))
* **security:** harden runtime control surface ([d443d48](https://github.com/oaslananka-lab/fovux/commit/d443d483effc4697c982158854aef7a5d9f7169f))

## [4.1.5](https://github.com/oaslananka-lab/fovux/compare/fovux-mcp-v4.1.4...fovux-mcp-v4.1.5) (2026-05-08)


### Bug Fixes

* correct cwd path for smoke tests ([6eeb2c3](https://github.com/oaslananka-lab/fovux/commit/6eeb2c3cc74050bfc42a1ed5a0c1a340cae70f3c))
* **dataset:** avoid recursive root scans in format detection ([e58833a](https://github.com/oaslananka-lab/fovux/commit/e58833a95d5f204c54870ac016b1b8a421216654))
* keep docker image buildable on slim base ([07cda6c](https://github.com/oaslananka-lab/fovux/commit/07cda6c27b3e6080a24a614f2768fce4bf49315c))
* **release:** align grouped release automation ([dd310b3](https://github.com/oaslananka-lab/fovux/commit/dd310b37b8bcd48d63b942e85d8ee625bf47cc23))
* **release:** keep uv lock version synced ([dcbc8d2](https://github.com/oaslananka-lab/fovux/commit/dcbc8d2cf82fc921b802acdb18ebf1e85739561c))
* resolve ruff and eslint errors failing the CI ([edfd82b](https://github.com/oaslananka-lab/fovux/commit/edfd82b4fb4da324a316e49e47a982e8aebc6da7))

## [4.1.4] - 2026-04-29

### Changed

- Version-aligned patch release with Fovux Studio 4.1.4.

## [4.1.3] - 2026-04-29

### Security

- Pin the Docker base image by digest so image builds are reproducible and Trivy scans the exact
  release runtime surface.
- Revalidated the backend package and runtime image after the final supply-chain hardening pass.

## [4.1.2] - 2026-04-29

### Fixed

- Dataset format auto-detection now checks only conventional shallow VOC annotation locations
  instead of recursively scanning arbitrary roots, so fuzzed paths such as `/` fail quickly and
  safely.

### Security

- Hardened adversarial dataset path handling caught by the tool-input fuzz suite.

## [4.1.1] - 2026-04-28

### Added

- Canonical `/runs/{run_id}/stream` SSE metrics endpoint while preserving `/runs/{run_id}/metrics`.
- Dataset inspection fields for missing-label images and normalized bounding-box size buckets.
- GPU memory details in structured doctor diagnostics.

### Changed

- Coverage enforcement is raised to 92% with focused tests for export, eval, benchmark, dataset,
  doctor, and HTTP streaming behavior.
- The container image installs only the runtime system package it needs (`libgomp1`) and upgrades
  pip to a pinned non-vulnerable version during image build.

### Security

- Trivy image scanning now ignores upstream-unfixed Debian CVEs with no fixed package available,
  while still failing on actionable fixed CRITICAL/HIGH vulnerabilities.
- Removed unnecessary Mesa/OpenGL package installation from the runtime image, closing the critical
  Mesa code-scanning alerts produced by the previous image.

## [4.1.0] - 2026-04-27

### Added

- `/health` response now includes `service` field for cross-package identification.
- JSON Schema export for every MCP tool input (37 schemas in `schemas/tools/`).
- MCP Registry manifest (`server.json`) and Smithery manifest (`smithery.yaml`).
- Tool documentation completeness gate: all 37 tools now have docs pages.
- Real-server integration tests in CI.
- Nightly compatibility job testing against latest upstream dependencies.
- LLM input fuzzing via Hypothesis and explicit path-traversal security tests.
- Cross-OS CI matrix covering Ubuntu, macOS, and Windows.

### Changed

- Version alignment: all version sources unified to `4.1.0` with CI enforcement via `scripts/check_versions.py`.
- Removed committed build artifacts (htmlcov, coverage.xml, junit.xml) and hardened `.gitignore`.

### Security

- Sigstore signing and SLSA Level 3 provenance for wheel and sdist artifacts.
- Tool input fuzzing covers path traversal, reserved characters, and oversized strings.

## [3.0.0] - 2026-04-27

### Added

- new roadmap tools for dataset augmentation, visual model comparison, run archiving, ensemble inference, active learning, distillation, MLflow sync, and live training adjustment
- structured `ErrorDetail` HTTP serialization and archived run metadata
- expanded `fovux_doctor` checks for CUDA/CuDNN, disk capacity, AGPL notice, active runs, CPU/RAM snapshot, and requirements
- contract, chaos, security, and public tool-boundary tests

### Changed

- `train_start` now supports `force` and `max_concurrent_runs`, writes PID atomically, rejects unsafe duplicate runs, and records spawn failures
- SQLite run registry now enables WAL, normal synchronous mode, and foreign keys
- HTTP tool invocation now applies per-tool rate limits
- INT8 quantization validates calibration datasets before export
- CI and local quality gates now enforce strict markers, timeout, 90% backend coverage, Bandit, and pip-audit

### Fixed

- worker termination now writes both `status.json` and registry terminal state
- RTSP save validation requires explicit output path and reconnect attempts are configurable
- raw library exceptions are wrapped at the tool boundary

## [2.0.0] - 2026-04-22

### Added

- authenticated local HTTP transport with persisted bearer token and `rotate-token`
- watch-based SSE streaming with `metrics.jsonl` as the preferred live metrics source
- `/metrics` Prometheus-style endpoint behind an explicit `--metrics` flag
- export history JSONL entries for ONNX, TFLite, and INT8 artifacts
- `run_delete` and `run_tag` tools for Studio context actions
- strict YOLO `data.yaml` validation before training and quantization
- SPDX SBOM generation and release preflight scripts for Azure DevOps

### Changed

- training stores runtime PID in `pid.txt` instead of rewriting `params.json`
- HTTP tool proxy runs blocking tools off the asyncio event loop
- `model_list` scans known artifact locations instead of recursively walking entire run trees
- output-writing tools now validate that artifacts stay in allowed local roots

### Fixed

- ONNX parity checks now compare raw model outputs and fail loudly on runtime errors
- RTSP inference uses reconnect backoff, bounded queues, dynamic FPS, and no Pydantic mutation
- dataset split math now guarantees split counts sum to the input size
- YOLO/COCO conversion preserves splits and detects category conflicts

### Security

- token auth is required for every HTTP endpoint except `/health`
- `data.yaml` parsing uses safe YAML rules and rejects unsafe tags/path escapes
- release publish remains disabled unless maintainer-set manual gates are enabled

## [1.0.0] - 2026-04-21

### Added

- structured logging via `core.logging` and tool lifecycle logging via `core.tooling`
- safe local path validation and configurable file-size limits
- HTTP metrics SSE at `GET /runs/{run_id}/metrics`
- HTTP tool proxy at `POST /tools/{name}`
- docs site expansion with per-tool pages, recipes, ADRs, and API reference
- property-based tests, benchmark coverage, and slow E2E training scaffolding
- Azure docs validation stage, optional slow validation stage, and SBOM generation

### Changed

- dataset tool format fallbacks now return explicit `FovuxDatasetFormatError` guidance
- CLI and HTTP startup now use the shared structured logger
- `train_status` exposes reusable metric parsing helpers for HTTP and Studio
- run registry uses `NullPool` to avoid lingering SQLite connections in tooling and tests
- Fovux Studio now bundles real React webviews for dashboard, dataset inspector, export wizard, and run comparison

### Fixed

- stale stderr logger binding under pytest capture
- `run_compare` circular import with `train_status`
- VS Code build output now emits `out/webviews/*/main.js` for packaged panels
