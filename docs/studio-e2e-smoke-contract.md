# Studio E2E Smoke Contract

Fovux Studio quality must include real extension-host smoke coverage in addition to unit tests.

## Required coverage

- Built VSIX can be packaged and installed by the release verification flow.
- `test:e2e` is reserved for VS Code test-host execution.
- Unit smoke tests cover activation, contributed commands, webview HTML loading, command palette wiring, LM tool registration, Workspace Trust limitations, and backend-offline UI states.
- Release/verification workflows archive VSIX, verification reports, logs, and evidence artifacts on failure.
- No telemetry should be required for tests or onboarding flows.

## Local commands

```bash
cd fovux-studio
pnpm run typecheck
pnpm exec eslint src test
pnpm run test
pnpm run package
pnpm run test:e2e
```
