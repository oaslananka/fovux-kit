# Fovux Studio

[![Repository](https://img.shields.io/badge/repo-oaslananka%2Ffovux-black?logo=github)](https://github.com/oaslananka/fovux)
[![Install](https://img.shields.io/badge/install-source-blue.svg)](https://github.com/oaslananka/fovux)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

Visual companion for [Fovux MCP](https://github.com/oaslananka/fovux/tree/main/fovux-mcp), focused on the daily loop of local YOLO work: start runs, watch metrics, inspect datasets, compare checkpoints, and export deployment artifacts.

## Status

Packaged releases are produced by the `oaslananka-lab/fovux` release pipeline and mirrored
to `oaslananka/fovux`. Use the Fovux Studio Marketplace/Open VSX release for normal installs, or package
from source when developing the extension.

## Features

- **Run Dashboard** — live metric overlays driven by the local SSE endpoint
- **Training Launcher** — start local YOLO runs from a guarded webview form
- **Dataset Inspector** — class distribution, dataset actions, and sample previews
- **Export Wizard** — ONNX/TFLite export with quantization-aware flows
- **Exports View** — review `FOVUX_HOME/exports.jsonl` history
- **Run Comparison** — compare tracked runs without leaving VS Code

## Screenshots

![Fovux Dashboard](https://raw.githubusercontent.com/oaslananka/fovux/refs/heads/main/fovux-studio/resources/screenshots/dashboard.png)

![Fovux Dataset Inspector](https://raw.githubusercontent.com/oaslananka/fovux/refs/heads/main/fovux-studio/resources/screenshots/dataset-inspector.png)

![Fovux Export Wizard](https://raw.githubusercontent.com/oaslananka/fovux/refs/heads/main/fovux-studio/resources/screenshots/export-wizard.png)

## Requirements

- [fovux-mcp](https://github.com/oaslananka/fovux/tree/main/fovux-mcp) installed from this repository
- VS Code ≥ 1.98
- Node `24.14.1` LTS with Corepack-enabled `pnpm@10.33.0`

## Install

```bash
git clone https://github.com/oaslananka/fovux
cd fovux/fovux-studio
corepack enable
corepack prepare pnpm@10.33.0 --activate
pnpm install --frozen-lockfile
pnpm verify
pnpm dlx @vscode/vsce@3.9.1 package --out fovux-studio.vsix --no-dependencies
code --install-extension fovux-studio.vsix
```

## Usage

1. Open the Fovux activity bar icon in VS Code.
2. Run `Fovux: Start Local Server`.
3. Use `Fovux: Start Training...`, Dashboard, Dataset Inspector, Export Wizard, or Compare Runs.

If you prefer an external terminal, start the backend with:

```bash
fovux-mcp serve --http --tcp --metrics
```

Studio uses the same `FOVUX_HOME` as the backend. Set `fovux.home` in VS Code settings when you want a workspace-specific demo directory.

For documentation source, see [fovux-mcp/docs](https://github.com/oaslananka/fovux/tree/main/fovux-mcp/docs).

## License

Apache-2.0
