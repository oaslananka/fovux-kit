# Studio Executable VSIX E2E Contract

Fovux Studio quality includes a real VS Code extension-host lane in addition to fast Vitest unit
coverage. The executable lane tests the **installed VSIX**, not the source checkout passed as the
extension-under-development.

## Required coverage

Each E2E run packages `fovuxstudiokit.vsix`, installs it through the downloaded VS Code CLI into an
isolated extensions directory, and launches a separate minimal harness extension. The suite verifies:

- the loaded `oaslananka.fovuxstudiokit` extension path is the installed VSIX directory;
- activation succeeds and all contributed commands are registered;
- the generic Language Model tool is registered when the VS Code LM API is available;
- the real dashboard webview opens and returns the same backend-offline initial state rendered to the
  webview;
- Workspace Trust is true in the explicit trusted run and false in the fresh Restricted Mode run;
- risky server startup is rejected before process creation in an untrusted workspace;
- the runtime contract reports **No telemetry** (`telemetryEnabled: false`).

## Isolation model

The runner pins VS Code `1.129.1` and creates independent directories per scenario:

- `extensions/` contains the installed target VSIX;
- `user-data/` prevents machine/user settings from affecting results;
- `fovux-home/` prevents access to a developer's real auth token or runs;
- an unused loopback port (`65534`) produces the deterministic backend-offline state.

Trusted mode uses `--disable-workspace-trust`. Untrusted mode deliberately omits that switch and opens
an isolated folder with a fresh user-data directory. `@vscode/test-electron` is used for downloading
VS Code and resolving its CLI, while the extension-host process is launched directly because the
library's `runTests()` helper always adds `--disable-workspace-trust` and therefore cannot exercise
Restricted Mode.

## Local commands

Static contract only, with no VS Code download:

```bash
task studio:e2e:check
```

Executable run:

```bash
cd fovux-studio
corepack enable
corepack prepare pnpm@10.34.1 --activate
pnpm install --frozen-lockfile --ignore-scripts
pnpm run test:e2e:ci
```

Linux requires an X display. The GitHub workflow uses:

```bash
xvfb-run -a -s "-screen 0 1440x900x24" pnpm run test:e2e:ci
```

## Evidence and failure handling

Runtime evidence is written under `fovux-studio/artifacts/studio-e2e/`:

- `trusted/extension-host.log` and `untrusted/extension-host.log`;
- a `result.json` for each mode;
- a failure screenshot captured with `scrot` before the VS Code process exits;
- the exact `fovuxstudiokit.vsix` tested by CI.

The `Studio packaged VSIX E2E` workflow uploads these files with `if: always()` so a failed activation,
webview, trust, or offline assertion remains diagnosable. Local artifacts and downloaded VS Code
binaries are ignored by Git.
