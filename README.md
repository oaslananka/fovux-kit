# Fovux

<p align="center">
  <strong>Local-first YOLO workbench for edge AI.</strong>
</p>

<p align="center">
  <a href="https://www.buymeacoffee.com/oaslananka">
    <img src="https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=%E2%98%95&slug=oaslananka&button_colour=FFDD00&font_colour=000000&font_family=Arial&outline_colour=000000&coffee_colour=ffffff" alt="Buy me a coffee" />
  </a>
</p>

[![Org CI/CD](https://github.com/oaslananka/fovux-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/oaslananka/fovux-kit/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/fovux-mcp)](https://pypi.org/project/fovux-mcp/)
[![npm](https://img.shields.io/npm/v/fovux-mcp)](https://www.npmjs.com/package/fovux-mcp)
[![Marketplace](https://img.shields.io/visual-studio-marketplace/v/oaslananka.fovuxstudiokit)](https://marketplace.visualstudio.com/items?itemName=oaslananka.fovuxstudiokit)
[![Python 3.12-3.14](https://img.shields.io/badge/Python-3.12_|_3.13_|_3.14-blue)](https://pypi.org/project/fovux-mcp/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## What is Fovux?

Fovux is a local-first vision workbench for YOLO datasets, training, evaluation, export, and edge inference. It combines the Python backend package `fovux-mcp` 1.6.2, the npm wrapper `fovux-mcp` 1.6.2, and the VS Code companion `Fovux Studio` 1.5.1 to streamline the computer vision engineering lifecycle.

## Why developers use it

- **Local-first**: No hosted control plane required. Your datasets and models stay entirely on your local machine or trusted infrastructure.
- **End-to-end YOLO lifecycle**: From raw image to optimized ONNX/TensorRT edge artifact, Fovux manages the complexity.
- **MCP-native automation**: Exposes the tool surface over MCP stdio for agent clients, while Fovux Studio uses a separate local HTTP/SSE API for dashboards and guarded UI workflows.
- **VS Code Studio**: Visual workflows directly in your editor for tracking runs, visualizing performance, and evaluating datasets.
- **Reproducible local runs**: Consistent configurations that you can share, compare, and audit.
- **Export and edge inference focus**: Export your models seamlessly to production-ready formats.
- **Privacy-first by default**: Fovux contains no hidden telemetry.

## 60-second quickstart

Ensure you have Python 3.12 through 3.14 installed. Install the backend globally using `uv`:

```bash
uv tool install fovux-mcp
fovux doctor
```

`fovux-mcp` is the primary CLI alias used by Fovux Studio and MCP clients. The shorter `fovux`
alias points to the same Typer application for direct terminal use.
npm users can install the wrapper package with `npm install -g fovux-mcp`; it delegates to
the matching Python package through `uvx`.

Initialize your Fovux environment and start the MCP server:

```bash
fovux-mcp serve --http
```

Install the VS Code extension, open the command palette (`Ctrl+Shift+P`), and type `Fovux: Start Training...` to begin your first run.

## Install

### Using `uv` (Recommended)

```bash
uv tool install fovux-mcp
```

### Using npm

```bash
npm install -g fovux-mcp
```

### Fovux Studio (VS Code Extension)

Search for **Fovux Studio** in the VS Code Marketplace or Open VSX, or install via the CLI:

```bash
code --install-extension oaslananka.fovuxstudiokit
```

## MCP client configuration

To connect an MCP desktop client to Fovux, add the following to your MCP client configuration (`mcp_config.json`):

```json
{
    "mcpServers": {
        "fovux": {
            "command": "fovux-mcp",
            "args": []
        }
    }
}
```

## Fovux Studio

Fovux Studio provides a visual layer over your Fovux environment directly inside VS Code:

- **Runs Dashboard**: Monitor training metrics, GPU usage, and epoch progress in real-time.
- **Dataset Inspector**: Analyze your YOLO annotations and locate missing labels.
- **Export Wizard**: Convert your models to ONNX, TensorRT, or TFLite with optimal shapes.
- **Timeline & Compare**: Diff your runs to understand regression or progress.

Use the VS Code Command Palette (`Cmd/Ctrl+Shift+P`) and type `Fovux:` to discover available commands.

## Core tools

Fovux MCP 1.6.2 exposes 47 local tools across dataset inspection, validation, active learning, training, evaluation, export, quantization, inference, benchmarking, run management, policy/audit, and support-bundle workflows.

The generated complete tool list lives in [`fovux-mcp/README.md`](fovux-mcp/README.md) and the MkDocs site; CI now fails if a registered tool is missing from docs, the schema snapshot, policy metadata, Studio mappings, or the MkDocs navigation.

## Architecture

Fovux separates concerns across three core components:

1. **Fovux Core**: The underlying Python engine interfacing with YOLO and local hardware.
2. **Fovux MCP Server**: The stdio MCP server exposing Fovux Core to AI agents, plus the Fovux Studio local API/custom REST+SSE bridge used by Fovux Studio. A standards-compliant Streamable HTTP MCP endpoint is tracked separately in the `v1.4.0 - MCP Conformance & Agent Safety` milestone.
3. **Fovux Studio**: The React/TypeScript VS Code extension for human interaction.

[Read more about the architecture in the docs](docs/architecture.md)

## Security and privacy

Fovux is built for enterprise privacy. **No telemetry is collected by default.** Data stays exactly where you put it, and no analytics payloads are sent to external services unless you explicitly configure third-party integrations (like W&B).

## CI/CD and release model

Fovux maintains a secure GitHub Actions release model in this repository:

- `oaslananka/fovux-kit`: The source of truth for code, issues, pull requests, CI, and releases.
- `.github/workflows`: The active CI, security, release, and registry publishing workflows.
- Protected GitHub environments gate PyPI, npm, Marketplace, and Open VSX publishing.

All releases are created by release-please from Conventional Commits, gated by CI, and published from GitHub Actions with checksums, SBOMs, and provenance.

## Repository operations

Repository operations, runtime compatibility, branch protection, developer bootstrap, and the release
process are documented in [docs/repository-operations.md](docs/repository-operations.md),
[docs/runtime-compatibility.md](docs/runtime-compatibility.md),
[docs/development.md](docs/development.md),
[docs/branch-protection.md](docs/branch-protection.md), and
[docs/release-process.md](docs/release-process.md). Local environment variable names are listed in
[`.env.example`](.env.example); publishing credentials remain in protected GitHub Actions secrets.

For a fresh development checkout on Linux/macOS:

```bash
scripts/bootstrap-dev.sh --install-deps --hooks
task ci
```

## Roadmap

- `v1.3.1 - Stabilization & Documentation Truth`: documentation drift, local DX, registry verification, release metadata, and fail-fast quality gates.
- `v1.4.0 - MCP Conformance & Agent Safety`: official MCP transport decision, conformance tests, schema snapshots, and agent approval safety.
- `Studio Workflow & Dataset Intelligence`: guided dataset→training→evaluation→export workflows and Studio e2e smoke coverage.
- `v1.6.0 - Edge Export & Deployment Intelligence`: current export matrix, target profiles, benchmark reproducibility, and quantization workflow.
- `v2.0.0 - Extensibility, Supply Chain & Ecosystem Readiness`: plugin/API stability, trusted publishing, attestations, threat model, and marketplace release evidence.

## Contributing

We welcome contributions! Please read our [Contributing Guidelines](CONTRIBUTING.md) to get started.

## License

Fovux is released under the [Apache-2.0 License](LICENSE).
