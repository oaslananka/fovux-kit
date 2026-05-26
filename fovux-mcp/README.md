# Fovux MCP

**From dataset to deployed ONNX, in one conversation.**

[![Primary CI](https://img.shields.io/badge/ci-Azure%20DevOps-blue.svg)](https://github.com/oaslananka/fovux)
[![Repository](https://img.shields.io/badge/repo-oaslananka%2Ffovux-black?logo=github)](https://github.com/oaslananka/fovux)
[![Python 3.11-3.13](https://img.shields.io/badge/python-3.11%20to%203.13-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Install](https://img.shields.io/badge/install-source-blue.svg)](https://github.com/oaslananka/fovux)

Fovux is a professional-grade, open-source edge-AI computer vision workbench. It lets a computer vision practitioner run the full YOLO lifecycle through natural-language conversation with any MCP-compatible AI client: dataset curation, training, evaluation, error analysis, quantization, export, on-device benchmarking, and RTSP inference.

> **Brand:** Fovux is the region of the retina responsible for sharp central vision. We help you see your models clearly.

## Why Fovux?

|                               | Fovux | Ultralytics Platform | GongRzhe/YOLO-MCP |
| ----------------------------- | ----- | -------------------- | ----------------- |
| Local-first, no account       | ✅    | ❌                   | ✅                |
| Full lifecycle (train→deploy) | ✅    | ✅                   | ❌                |
| Error analysis                | ✅    | Partial              | ❌                |
| INT8 quantization report      | ✅    | ❌                   | ❌                |
| VS Code companion             | ✅    | ❌                   | ❌                |
| RTSP live inference           | ✅    | ❌                   | ❌                |
| Open source                   | ✅    | ❌                   | ✅                |

## Status

Packaged releases are produced by the `oaslananka-lab/fovux` release pipeline and mirrored
to `oaslananka/fovux`. Install fovux-mcp from PyPI when you need the signed release artifact, or use
the source workflow below for development.

## Install From Source

```bash
git clone https://github.com/oaslananka/fovux
cd fovux/fovux-mcp
uv sync --frozen --extra dev
```

The Apache-2.0 core keeps YOLO engine dependencies optional. Install the `yolo` extra only when
the Ultralytics backend and its separate AGPL/commercial terms are appropriate for your use case:

```bash
uv sync --frozen --extra dev --extra yolo
```

## Quick start (5 minutes)

See [docs/getting-started.md](docs/getting-started.md) for the full tutorial.

```bash
# 1. Install from source
git clone https://github.com/oaslananka/fovux
cd fovux/fovux-mcp
uv sync --frozen --extra dev --extra yolo
uv run fovux-mcp doctor

# 2. Configure your MCP client (example: Cursor / Windsurf / VS Code)
# Add to your MCP client settings:
#   "fovux": { "command": "fovux-mcp" }

# 3. Start chatting
# "Inspect my dataset at ~/data/coco128"
# "Train yolov8n on it for 50 epochs"
# "Run error analysis on the best checkpoint"
# "Export to ONNX and benchmark on CPU"
```

For Studio or HTTP demos, start the local transport explicitly:

```bash
uv run fovux-mcp serve --http --tcp --metrics
```

## MCP client configuration

### Cursor / Windsurf

```json
{
  "mcpServers": {
    "fovux": {
      "command": "fovux-mcp",
      "env": {
        "FOVUX_HOME": "~/.fovux"
      }
    }
  }
}
```

### VS Code (with MCP extension)

```json
{
  "mcp.servers": {
    "fovux": {
      "command": "fovux-mcp"
    }
  }
}
```

## The tool set

Fovux MCP currently exposes 28 local tools.

<!-- fovux-tools:start -->

| Tool                       | Purpose                                                  |
| -------------------------- | -------------------------------------------------------- |
| `annotation_quality_check` | Find common YOLO annotation quality issues.              |
| `benchmark_latency`        | Measure p50/p95/p99 inference latency.                   |
| `dataset_convert`          | Convert datasets between supported formats.              |
| `dataset_find_duplicates`  | Detect duplicate images with perceptual hashing.         |
| `dataset_inspect`          | Inspect dataset structure, classes, and samples.         |
| `dataset_split`            | Create train/val/test splits.                            |
| `dataset_validate`         | Validate dataset integrity and label ranges.             |
| `eval_compare`             | Compare evaluation outputs.                              |
| `eval_error_analysis`      | Extract worst false-positive and false-negative samples. |
| `eval_per_class`           | Report per-class validation metrics.                     |
| `eval_run`                 | Run validation for a checkpoint.                         |
| `export_onnx`              | Export checkpoints to ONNX.                              |
| `export_tflite`            | Export checkpoints to TFLite.                            |
| `fovux_doctor`             | Report local environment health.                         |
| `infer_batch`              | Run batch inference over image folders.                  |
| `infer_image`              | Run single-image inference.                              |
| `infer_rtsp`               | Run live RTSP inference with reconnect handling.         |
| `model_list`               | List local checkpoints and exports.                      |
| `model_profile`            | Profile model size and complexity.                       |
| `quantize_int8`            | Create INT8 quantized artifacts.                         |
| `quantize_report`          | Compare quantized model quality.                         |
| `run_compare`              | Compare local training runs.                             |
| `run_delete`               | Delete non-running runs safely.                          |
| `run_tag`                  | Edit local run tags.                                     |
| `train_resume`             | Resume a stopped or failed run.                          |
| `train_start`              | Start detached YOLO training.                            |
| `train_status`             | Read current run status and metrics.                     |
| `train_stop`               | Stop a running training process.                         |

<!-- fovux-tools:end -->

## VS Code companion

Use [Fovux Studio in this repo](https://github.com/oaslananka/fovux/tree/main/fovux-studio) for visual run dashboards, dataset inspection, and an export wizard.

## Documentation

Docs source lives in [fovux-mcp/docs](https://github.com/oaslananka/fovux/tree/main/fovux-mcp/docs).
Generated `site/` output is a build artifact and is not committed.

```bash
uv run mkdocs build --strict
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributions welcome.

## License

Fovux core is Apache-2.0. The Ultralytics YOLO backend is optional and carries its own AGPL/commercial licensing boundary; install the `yolo` extra only when that backend is appropriate for your use case. See [LICENSE](LICENSE), [NOTICE](NOTICE), and [docs/adr/0003-ultralytics-adapter-boundary.md](docs/adr/0003-ultralytics-adapter-boundary.md).
