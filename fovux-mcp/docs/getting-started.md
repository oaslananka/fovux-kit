# Getting Started — Fovux in 5 Minutes

This quickstart walks through the end-to-end local workflow on a YOLO dataset.

## 1. Install From Source

```bash
git clone https://github.com/oaslananka/fovux
cd fovux/fovux-mcp
uv sync --frozen --extra dev
```

## 2. Register Fovux In Your MCP Client

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

## 3. Inspect The Dataset

Prompt your MCP client with:

> Inspect my dataset at `~/data/mini_yolo` and summarize the class balance.

Fovux uses `dataset_inspect` to return class counts, orphan warnings, and sample images.

## 4. Start Training

> Train `yolov8n.pt` on this dataset for 20 epochs and tag it `baseline`.

Fovux uses `train_start`. The call returns immediately while training continues in the background.

## 5. Watch Progress

> Check the current status of my latest run.

Fovux uses `train_status`. In Fovux Studio, the live dashboard can subscribe to `/runs/{run_id}/metrics`.

## 6. Evaluate And Diagnose

> Evaluate the best checkpoint and explain the main failure modes.

Use `eval_run`, `eval_per_class`, and `eval_error_analysis` to understand both headline metrics and the likely causes behind misses.

## 7. Export And Benchmark

> Export the best checkpoint to ONNX and benchmark it on CPU.

This combines `export_onnx` and `benchmark_latency`, producing a deployable artifact plus p50/p95/p99 latency numbers.

## 8. Open Fovux Studio

Build the extension from source:

```bash
cd ../fovux-studio
pnpm install --frozen-lockfile
pnpm build
```

Then open the dashboard, dataset inspector, or export wizard inside VS Code.
