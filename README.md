# Fovux

<p align="center">
  <strong>Local-first YOLO workbench for edge AI.</strong>
</p>

[![Org CI/CD](https://github.com/oaslananka-lab/fovux/actions/workflows/ci.yml/badge.svg)](https://github.com/oaslananka-lab/fovux/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/fovux-mcp)](https://pypi.org/project/fovux-mcp/)
[![Marketplace](https://img.shields.io/visual-studio-marketplace/v/oaslananka.fovux-studio)](https://marketplace.visualstudio.com/items?itemName=oaslananka.fovux-studio)
[![Python 3.11-3.13](https://img.shields.io/badge/Python-3.11_|_3.12_|_3.13-blue)](https://pypi.org/project/fovux-mcp/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## What is Fovux?

Fovux is a local-first vision workbench for YOLO datasets, training, evaluation, export, and edge inference. It seamlessly integrates a powerful Python MCP server (`fovux-mcp`) with a highly interactive VS Code companion (`Fovux Studio`) to streamline your computer vision engineering lifecycle.

## Why developers use it

- **Local-first**: No hosted control plane required. Your datasets and models stay entirely on your local machine or trusted infrastructure.
- **End-to-end YOLO lifecycle**: From raw image to optimized ONNX/TensorRT edge artifact, Fovux manages the complexity.
- **MCP-native automation**: Fully compatible with the Model Context Protocol (MCP) to automate AI workflows.
- **VS Code Studio**: Visual workflows directly in your editor for tracking runs, visualizing performance, and evaluating datasets.
- **Reproducible local runs**: Consistent configurations that you can share, compare, and audit.
- **Export and edge inference focus**: Export your models seamlessly to production-ready formats.
- **Privacy-first by default**: Fovux contains no hidden telemetry.

## 60-second quickstart

Ensure you have Python 3.11+ installed. Install the backend globally using `uv`:

```bash
uv tool install fovux-mcp
fovux doctor
```

`fovux-mcp` is the primary CLI alias used by Fovux Studio and MCP clients. The shorter `fovux`
alias points to the same Typer application for direct terminal use.

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

### Fovux Studio (VS Code Extension)

Search for **Fovux Studio** in the VS Code Marketplace or Open VSX, or install via the CLI:

```bash
code --install-extension oaslananka.fovux-studio
```

## MCP client configuration

To connect an MCP desktop client to Fovux, add the following to your MCP client configuration (`mcp_config.json`):

```json
{
  "mcpServers": {
    "fovux": {
      "command": "fovux-mcp",
      "args": ["serve"]
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

| Tool              | Description                                                    |
| ----------------- | -------------------------------------------------------------- |
| `train_start`     | Launch a new YOLO training run with specified hyperparameters. |
| `train_status`    | Get metrics and status for an ongoing or completed run.        |
| `dataset_inspect` | Analyze a YOLO dataset and generate quality reports.           |
| `eval_compare`    | Compare metrics between two runs.                              |
| `export_onnx`     | Export a PyTorch weight file to an ONNX graph.                 |
| `fovux_doctor`    | Generate a diagnostic health report.                           |

_(For a full list of tools, run `fovux-mcp --help`)_

Both CLI aliases are intentional:

- `fovux-mcp`: primary alias for MCP clients, Studio, automation, and docs.
- `fovux`: convenience alias for humans typing local commands.

## Architecture

Fovux separates concerns across three core components:

1. **Fovux Core**: The underlying Python engine interfacing with YOLO and local hardware.
2. **Fovux MCP Server**: The standardized HTTP/stdio layer exposing Fovux Core to AI agents.
3. **Fovux Studio**: The React/TypeScript VS Code extension for human interaction.

[Read more about the architecture in the docs](docs/architecture.md)

## Security and privacy

Fovux is built for enterprise privacy. **No telemetry is collected by default.** Data stays exactly where you put it, and no analytics payloads are sent to external services unless you explicitly configure third-party integrations (like W&B).

## CI/CD and release model

Fovux maintains a secure release model:

- `oaslananka/fovux`: The primary developer-facing public repository.
- `oaslananka-lab/fovux`: The GitHub organization repository containing the authoritative CI/CD pipelines and release gates.
- `dev.azure.com/...`: An enterprise public mirror.

All releases are created by release-please from Conventional Commits, gated by CI, and published from GitHub Actions with checksums, SBOMs, and provenance.

## Repository operations

Repository operations, Doppler secret management, branch protection, and the release process are documented in [docs/repository-operations.md](docs/repository-operations.md), [docs/doppler-setup.md](docs/doppler-setup.md), [docs/branch-protection.md](docs/branch-protection.md), and [docs/release-process.md](docs/release-process.md).

## Roadmap

- Multi-GPU distributed training orchestration
- CoreML optimization support for Apple Silicon edge devices
- Extended integration with Hugging Face Hub

## Contributing

We welcome contributions! Please read our [Contributing Guidelines](CONTRIBUTING.md) to get started.

## License

Fovux is released under the [Apache-2.0 License](LICENSE).
