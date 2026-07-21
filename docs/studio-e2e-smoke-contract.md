# Studio Executable VSIX E2E Contract

Fovux Studio quality includes a real VS Code extension-host lane in addition to fast Vitest unit
coverage. The executable lane tests the **installed VSIX**, not the source checkout passed as the
extension-under-development.

## Required coverage

Each E2E run packages `fovuxstudiokit.vsix`, installs it through the downloaded VS Code CLI into an
isolated extensions directory, and launches a separate minimal harness extension. The suite verifies:

- the loaded `oaslananka.fovuxstudiokit` extension path is the installed VSIX directory;
- activation succeeds and all contributed commands are registered;
- the runtime contract reports **No telemetry** (`telemetryEnabled: false`);
- Workspace Trust is true in the explicit trusted run and false in the fresh Restricted Mode run;
- risky server startup is rejected before process creation in an untrusted workspace;
- backend-offline state is returned by the real dashboard command;
- an auth-token mismatch is detected against an isolated fake local HTTP server before a replacement
  server process can be spawned;
- the packaged dashboard bundle loads, sends a real `webviewReady` message to the extension, and uses
  the exact Content Security Policy assigned to its document;
- `vscode.lm.invokeTool` invokes the installed extension's `fovux_run_doctor` tool through an isolated
  fake local HTTP server and preserves the expected bearer-token boundary.

## Isolation and dependency model

The runner pins VS Code `1.129.1` and creates independent directories per scenario:

- `extensions/` contains the installed target VSIX;
- `user-data/` prevents machine/user settings from affecting results;
- `fovux-home/` prevents access to a developer's real auth token or runs;
- an unused loopback port (`65534`) produces the deterministic backend-offline state;
- random loopback ports host short-lived fake servers for auth-token mismatch and Language Model tool
  invocation checks.

Trusted mode uses `--disable-workspace-trust`. Untrusted mode deliberately omits that switch and opens
an isolated folder with a fresh user-data directory.

The E2E harness is dependency-free beyond the Studio project's existing TypeScript and VS Code type
packages. Node.js built-in APIs download the official pinned VS Code archive, extract it with the host
`tar` utility, install the VSIX, launch the extension host, host fake loopback servers, and run
assertions. No Mocha or `@vscode/test-electron` dependency tree is added to the lockfile. This keeps the
test supply-chain surface small and allows the repository's OSV and OpenSSF dependency policies to
remain strict.

## Webview diagnostics boundary

The dashboard records the exact bundle URI and Content Security Policy before assigning its HTML. The
packaged React bundle sends `webviewReady` after mounting. The extension records that handshake and
exposes read-only diagnostics through the activation API. The E2E harness waits for this signal and
checks that the CSP:

- defaults to no resource access;
- permits only loopback HTTP connections needed by the local backend;
- uses a per-document script nonce;
- does not permit `unsafe-eval`.

This boundary proves more than command registration: the packaged JavaScript bundle loaded inside a
real webview and exchanged a message with the installed extension.

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
- a `result.json` for each mode, including each assertion's passed or skipped state;
- a failure screenshot captured with `scrot` before the VS Code process exits;
- the exact `fovuxstudiokit.vsix` tested by CI.

The `Studio packaged VSIX E2E` workflow uploads these files with `if: always()` so a failed activation,
webview, trust, offline, auth, or Language Model assertion remains diagnosable. Local artifacts and
downloaded VS Code binaries are ignored by Git.
