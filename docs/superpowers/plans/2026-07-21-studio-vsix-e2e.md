# Studio Packaged VSIX E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exercise the packaged Fovux Studio VSIX in real isolated VS Code instances and verify activation, contributed commands, backend-offline and auth-token mismatch behavior, a CSP-protected dashboard message handshake, Language Model tool invocation, Workspace Trust restrictions, no-telemetry runtime state, and failure evidence.

**Architecture:** Package the production extension, install that VSIX into an isolated extensions directory with a pinned VS Code CLI downloaded through Node.js built-in APIs, and run a separate minimal harness extension without a test framework dependency. Trusted and untrusted modes use independent workspaces and user-data directories. The production extension exposes read-only runtime and dashboard diagnostics, while isolated loopback servers exercise auth rejection and Language Model tool calls.

**Tech Stack:** VS Code 1.129.1, Node.js built-in fetch/HTTP/process APIs, TypeScript 5.9, pnpm 10.34.1, xvfb, scrot, GitHub Actions.

## Global Constraints

- The E2E target must be the installed `fovuxstudiokit.vsix`, never the source extension development path.
- Trusted and untrusted scenarios must use separate VS Code processes, fresh user data, and isolated extension directories.
- Tests must not start a real Fovux server or contact non-local services.
- The test HTTP port must be an unused loopback port and must produce a deterministic offline result.
- No telemetry dependency or external beacon is permitted.
- CI must upload logs, JSON results, and a screenshot on failure.
- Existing fast Vitest tests remain the normal local unit-test path; executable E2E runs in a dedicated workflow.

---

### Task 1: Define executable E2E contracts

**Files:**
- Create: `fovux-mcp/tests/unit/test_studio_e2e_contract.py`
- Modify: `scripts/check_studio_e2e_smoke.py`

**Interfaces:**
- Consumes: `fovux-studio/package.json`, `.github/workflows/studio-e2e.yml`, and E2E source files.
- Produces: a static contract that rejects mock-only `test:e2e` configurations and missing artefact capture.

- [x] **Step 1: Write failing tests** asserting a pinned dependency-free VS Code runner, trusted/untrusted modes, installed-VSIX path, offline and auth mismatch behavior, webview handshake/CSP, Language Model invocation, trust restrictions, and always-uploaded failure artefacts.
- [x] **Step 2: Run** the focused contract tests and verify RED before the executable files and workflow exist.
- [x] **Step 3: Extend** `scripts/check_studio_e2e_smoke.py` to semantically validate the same files and package scripts.
- [x] **Step 4: Keep the contract RED** until Tasks 2–5 provide the implementation.

### Task 2: Add a stable extension runtime observation API

**Files:**
- Create: `fovux-studio/src/fovux/runtimeApi.ts`
- Modify: `fovux-studio/src/extension.ts`
- Modify: `fovux-studio/src/commands/openDashboard.ts`
- Modify: `fovux-studio/test/suite/extension.test.ts`

**Interfaces:**
- Produces: `FovuxStudioApi.getRuntimeState(): FovuxRuntimeState` plus read-only dashboard CSP/bundle/ready diagnostics.
- Produces: `openDashboard(context): Promise<DashboardInitialState>` so command callers observe the exact initial webview state.

- [x] **Step 1: Write Vitest tests** for the activation API, no-telemetry value, trust value, dashboard state, malformed manifest metadata, and the webview-ready diagnostics handshake.
- [x] **Step 2: Run the focused tests** and verify RED before the observation API and dashboard result exist.
- [x] **Step 3: Implement** runtime and dashboard diagnostics using package metadata, Workspace Trust, no-telemetry metadata, the assigned CSP, bundle URI, and real `webviewReady` messages.
- [x] **Step 4: Return** the rendered `DashboardInitialState` from `openDashboard`/`renderDashboard` and preserve production webview behavior.
- [x] **Step 5: Run** focused Vitest, lint, and typecheck.

### Task 3: Build the installed-VSIX test harness

**Files:**
- Create: `fovux-studio/test/e2e/run.mjs`
- Create: `fovux-studio/test/e2e/tsconfig.json`
- Create: `fovux-studio/test/e2e/harness/package.json`
- Create: `fovux-studio/test/e2e/harness/extension.js`
- Create: `fovux-studio/test/e2e/suite/index.ts`
- Create: `fovux-studio/test/e2e/suite/installedExtension.test.ts`
- Create: `fovux-studio/test/e2e/fixtures/trusted.code-workspace`
- Create: `fovux-studio/test/e2e/fixtures/untrusted/data.yaml`
- Modify: `fovux-studio/package.json`
- Modify: `fovux-studio/pnpm-lock.yaml`

**Interfaces:**
- Produces: `pnpm run test:e2e:compile` and `pnpm run test:e2e`.
- Runner inputs: `FOVUX_E2E_ARTIFACTS`, `FOVUX_E2E_MODE`, `FOVUX_E2E_EXTENSION_PATH`, and isolated test directories.
- Test output: `<artifacts>/<mode>/result.json`, `<artifacts>/<mode>/extension-host.log`, and failure screenshot.

- [x] **Step 1: Keep the executable harness dependency-free** beyond existing TypeScript and VS Code type packages; explicitly reject Mocha and `@vscode/test-electron`.
- [x] **Step 2: Implement the runner** with Node.js built-ins to download VS Code 1.129.1, install the built VSIX into isolated extension directories, and launch trusted/untrusted extension hosts directly.
- [x] **Step 3: Assert in the suite** installed path, activation, commands, offline dashboard state, CSP and `webviewReady` handshake, auth-token mismatch, and a real `vscode.lm.invokeTool` call through `fovux_run_doctor`.
- [x] **Step 4: Assert untrusted behavior** by checking `workspaceTrusted === false` and verifying `fovux.startServer` rejects before spawning a process.
- [x] **Step 5: Capture per-assertion JSON evidence** from the framework-free runner and call absolute-path `scrot` before the VS Code process exits when failures occur.
- [ ] **Step 6: Run trusted then untrusted E2E under the GitHub-hosted xvfb lane.**

### Task 4: Add a dedicated CI lane and artefact retention

**Files:**
- Create: `.github/workflows/studio-e2e.yml`
- Modify: `scripts/check_studio_e2e_smoke.py`
- Modify: `fovux-mcp/tests/unit/test_studio_e2e_contract.py`

**Interfaces:**
- Workflow check: `Studio packaged VSIX E2E`.
- Artefact: `studio-e2e-${{ github.run_id }}` uploaded with `if: always()`.

- [ ] **Step 1: Add SHA-pinned checkout/setup-node/upload-artifact actions**, Node 24.16.0, pnpm 10.34.1, `xvfb`, and `scrot` installation.
- [ ] **Step 2: Package VSIX** and run the executable harness under `xvfb-run -a`.
- [ ] **Step 3: Upload** E2E logs/results/screenshots and the tested VSIX on success or failure.
- [ ] **Step 4: Run** actionlint and zizmor; fix every high-severity finding.

### Task 5: Integrate developer commands and documentation

**Files:**
- Modify: `Taskfile.yml`
- Modify: `docs/studio-e2e-smoke-contract.md`
- Modify: `docs/development.md`
- Modify: `scripts/check_task_docs.py` only if needed by existing task-document contracts.

**Interfaces:**
- Produces: `task studio:e2e:check` for static contracts and `task studio:e2e` for executable local E2E.

- [ ] **Step 1: Add Task commands** that preserve the distinction between fast static checks and downloaded VS Code execution.
- [ ] **Step 2: Document** prerequisites, trusted/untrusted behavior, artifact paths, VS Code cache behavior, and failure debugging.
- [ ] **Step 3: Run** task/docs truth checks.

### Task 6: Full verification and pull request completion

**Files:** all files above.

- [ ] **Step 1: Run** Studio format, lint, typecheck, all Vitest tests, build, package, static E2E contract, and executable E2E.
- [ ] **Step 2: Run** focused Python tests, Ruff, strict mypy where applicable, actionlint, zizmor, docs truth, task docs, and `git diff --check`.
- [ ] **Step 3: Run** the full backend suite; distinguish any pre-existing worker-only stdio timeout by reproducing it on unchanged main if necessary.
- [ ] **Step 4: Open a PR closing #108.**
- [ ] **Step 5: Inspect and address Sonar, CodeQL, OSV, Socket, Codecov, review-thread, and other agent comments before merging.
