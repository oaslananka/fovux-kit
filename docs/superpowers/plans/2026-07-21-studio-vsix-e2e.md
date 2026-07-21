# Studio Packaged VSIX E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Exercise the packaged Fovux Studio VSIX in real isolated VS Code instances and verify activation, contributed commands, dashboard offline state, Workspace Trust restrictions, no-telemetry runtime state, and failure evidence.

**Architecture:** Package the production extension, install that VSIX into an isolated extensions directory with the downloaded VS Code CLI, and run a separate minimal harness extension through `@vscode/test-electron`. Trusted and untrusted modes use independent workspaces and user-data directories. The production extension exposes a small stable runtime API for trust/telemetry metadata, while dashboard command results expose the real offline initial state used by the webview.

**Tech Stack:** VS Code 1.129.1, `@vscode/test-electron` 3.0.0, Mocha 11.7.6, TypeScript 5.9, pnpm 10.34.1, xvfb, scrot, GitHub Actions.

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

- [ ] **Step 1: Write failing tests** asserting pinned VS Code/test dependencies, package/install runner files, trusted/untrusted modes, installed-VSIX path assertion, offline dashboard assertion, trust restriction assertion, and always-uploaded failure artefacts.
- [ ] **Step 2: Run** `cd fovux-mcp && uv run pytest -q tests/unit/test_studio_e2e_contract.py` and verify failure because executable files/workflow do not exist.
- [ ] **Step 3: Extend** `scripts/check_studio_e2e_smoke.py` to semantically validate the same files and package scripts.
- [ ] **Step 4: Keep the contract RED** until Tasks 2–5 provide the implementation.

### Task 2: Add a stable extension runtime observation API

**Files:**
- Create: `fovux-studio/src/fovux/runtimeApi.ts`
- Modify: `fovux-studio/src/extension.ts`
- Modify: `fovux-studio/src/commands/openDashboard.ts`
- Modify: `fovux-studio/test/suite/extension.test.ts`

**Interfaces:**
- Produces: `FovuxStudioApi.getRuntimeState(): FovuxRuntimeState` with `workspaceTrusted`, `telemetryEnabled`, `extensionVersion`, and `contributedCommands`.
- Produces: `openDashboard(context): Promise<DashboardInitialState>` so command callers observe the exact initial webview state.

- [ ] **Step 1: Write Vitest tests** for the returned activation API, no-telemetry value, trust value, and dashboard command result.
- [ ] **Step 2: Run the focused tests** and verify failure because `activate()` returns no API and dashboard returns `void`.
- [ ] **Step 3: Implement** the runtime API using `context.extension.packageJSON`, `vscode.workspace.isTrusted`, and the constant `telemetryEnabled: false`.
- [ ] **Step 4: Return** the rendered `DashboardInitialState` from `openDashboard`/`renderDashboard` without changing webview behavior.
- [ ] **Step 5: Run** focused Vitest, lint, and typecheck.

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

- [ ] **Step 1: Add exact dev dependencies** `@vscode/test-electron@3.0.0`, `mocha@11.7.6`, and `@types/mocha@10.0.10`.
- [ ] **Step 2: Implement the runner** to download VS Code 1.129.1, install the built VSIX through its CLI into an isolated extensions directory, and invoke the harness via `runTests` twice.
- [ ] **Step 3: Assert in the suite** that `oaslananka.fovuxstudiokit` is installed outside the repository, activates, returns the runtime API, registers all contributed commands, opens `Fovux Dashboard`, reports the loopback backend offline, and contributes `fovux_call_tool` when the LM API is available.
- [ ] **Step 4: Assert untrusted behavior** by checking `workspaceTrusted === false` and verifying `fovux.startServer` rejects before spawning a process.
- [ ] **Step 5: Capture evidence** from the Mocha runner and call `scrot` before the VS Code process exits when failures occur.
- [ ] **Step 6: Run trusted then untrusted E2E locally under xvfb.**

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
