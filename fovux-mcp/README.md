# Fovux MCP

**From dataset to deployed ONNX, in one conversation.**

[![Primary CI](https://github.com/oaslananka/fovux-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/oaslananka/fovux-kit/actions/workflows/ci.yml)
[![Repository](https://img.shields.io/badge/repo-oaslananka%2Ffovux--kit-black?logo=github)](https://github.com/oaslananka/fovux-kit)
[![Python 3.12-3.14](https://img.shields.io/badge/python-3.12%20to%203.14-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Install](https://img.shields.io/badge/install-source-blue.svg)](https://github.com/oaslananka/fovux-kit)

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

Packaged releases are produced by GitHub Actions in `oaslananka/fovux-kit`. Install fovux-mcp from
PyPI when you need the signed release artifact, or use the source workflow below for development.

## Install From Source

```bash
git clone https://github.com/oaslananka/fovux-kit
cd fovux-kit/fovux-mcp
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
git clone https://github.com/oaslananka/fovux-kit
cd fovux-kit/fovux-mcp
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

Fovux MCP 1.3.0 currently exposes 47 local tools.

<!-- fovux-tools:start -->

| Tool                            | Purpose                                                                                                    |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `active_learning_queue_list`    | List review queue entries from the SQLite database.                                                        |
| `active_learning_queue_rank`    | Rank unlabeled images by uncertainty using a YOLO checkpoint and populate the review queue.                |
| `active_learning_queue_submit`  | Submit label corrections for a queue entry, copy the image to the dataset, and write the YOLO label file.  |
| `active_learning_select`        | Rank unlabeled images by model uncertainty for annotation prioritization.                                  |
| `annotation_quality_check`      | Inspect YOLO labels for common annotation mistakes before a bad dataset wastes training time.              |
| `benchmark_latency`             | Measure local inference latency and throughput for a model artifact.                                       |
| `dataset_augment`               | Create a local augmented YOLO dataset copy using deterministic transforms.                                 |
| `dataset_convert`               | Convert between supported YOLO and COCO dataset layouts.                                                   |
| `dataset_find_duplicates`       | Perceptual hash duplicate detection for image datasets.                                                    |
| `dataset_inspect`               | Comprehensive dataset statistics for YOLO or COCO exports.                                                 |
| `dataset_split`                 | Create reproducible train, val, and test splits.                                                           |
| `dataset_validate`              | Deep integrity checks for YOLO datasets.                                                                   |
| `demo_init`                     | Initialize a demo workspace for first-run onboarding.                                                      |
| `deployment_advise`             | Analyze deployment readiness, preflight checks, parity, and benchmarks.                                    |
| `distill_model`                 | Start a student-model training run with teacher-model distillation metadata.                               |
| `eval_compare`                  | Evaluate multiple checkpoints on the same dataset and rank the results.                                    |
| `eval_error_analysis`           | Inspect confusion patterns and worst examples beyond headline metrics.                                     |
| `eval_per_class`                | Return a sorted per-class view over evaluation output.                                                     |
| `eval_run`                      | Run a validation pass on a checkpoint.                                                                     |
| `export_onnx`                   | Export a checkpoint to ONNX and optionally verify parity.                                                  |
| `export_reproducibility_bundle` | Export a reproducibility bundle zip file for a training run.                                               |
| `export_tflite`                 | Export a checkpoint to TFLite, optionally with INT8 enabled.                                               |
| `fovux_doctor`                  | Inspect the local Fovux environment before training, exporting, or opening Studio live views.              |
| `generate_support_bundle`       | Generate a redacted support bundle zip file containing system diagnostic information.                      |
| `get_policy_status`             | Retrieve the current security policy status and allowed tools for the active environment.                  |
| `infer_batch`                   | Run inference over an image directory and persist the detections as a reusable manifest.                   |
| `infer_ensemble`                | Run inference with multiple checkpoints and fuse the detections.                                           |
| `infer_image`                   | Run structured inference on a single image.                                                                |
| `infer_rtsp`                    | Run live inference over an RTSP stream with reconnection logic.                                            |
| `list_audit_events`             | Retrieve audit event logs from the local database.                                                         |
| `model_compare_visual`          | Generate visual comparison artifacts between two model checkpoints.                                        |
| `model_list`                    | List tracked checkpoints and exported model artifacts.                                                     |
| `model_profile`                 | Profile a checkpoint so you can choose between accuracy, size, and compute cost before training or export. |
| `quantize_int8`                 | Produce an INT8 ONNX export using a calibration dataset.                                                   |
| `quantize_report`               | Compare original and quantized checkpoints on the same evaluation set.                                     |
| `run_archive`                   | Archive a completed training run to a compressed file.                                                     |
| `run_compare`                   | Generate a markdown and PNG summary across multiple training runs.                                         |
| `run_delete`                    | Deletes a non-running training run from the SQLite registry and, by default, removes its run.              |
| `run_tag`                       | Replaces the tag list for a training run. Tags are stored in the local SQLite registry and used by.        |
| `set_policy_mode`               | Set the local security policy mode to adjust permissions and confirmation prompts.                         |
| `sync_to_mlflow`                | Sync a training run to a local or remote MLflow tracking server.                                           |
| `train_adjust`                  | Adjust hyperparameters of a running training run.                                                          |
| `train_preflight`               | Perform preflight checks and return a diagnostic training compatibility summary.                           |
| `train_resume`                  | Resume a stopped or failed run from its latest checkpoint.                                                 |
| `train_start`                   | Launch a non-blocking YOLO training subprocess.                                                            |
| `train_status`                  | Read the latest state and metrics for a tracked training run.                                              |
| `train_stop`                    | Stop a running training subprocess and mark the run as stopped.                                            |

<!-- fovux-tools:end -->

## VS Code companion

Use [Fovux Studio in this repo](https://github.com/oaslananka/fovux-kit/tree/main/fovux-studio) for visual run dashboards, dataset inspection, and an export wizard.

## Documentation

Docs source lives in [fovux-mcp/docs](https://github.com/oaslananka/fovux-kit/tree/main/fovux-mcp/docs).
Generated `site/` output is a build artifact and is not committed.

```bash
uv run mkdocs build --strict
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All contributions welcome.

## License

Fovux core is Apache-2.0. The Ultralytics YOLO backend is optional and carries its own AGPL/commercial licensing boundary; install the `yolo` extra only when that backend is appropriate for your use case. See [LICENSE](LICENSE), [NOTICE](NOTICE), and [docs/adr/0003-ultralytics-adapter-boundary.md](docs/adr/0003-ultralytics-adapter-boundary.md).
