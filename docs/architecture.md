# Fovux Architecture

Fovux is a local-first CV workbench with two primary packages:

- `fovux-mcp`: a Python FastMCP server that owns tools, training subprocesses, the SQLite run
  registry, local HTTP/SSE transport, and artifact generation.
- `fovux-studio`: a VS Code extension that renders run, model, export, dataset, and training
  workflows over the local server.

```mermaid
flowchart LR
  User["Engineer in VS Code"] --> Studio["VS Code Extension"]
  Studio --> CodeLens["CodeLens Provider: data.yaml"]
  Studio --> Decorations["File Decoration Provider: runs"]
  Studio --> Status["Status Bar Items: active runs, profile, privacy"]
  Studio --> Trees["Tree Views: Runs, Models, Exports, Doctor"]
  Studio --> Webviews["React Webviews"]
  Studio --> LMTools["Language Model Tools: 13"]
  Webviews --> Dashboard["Dashboard: SSE with polling fallback"]
  Webviews --> DatasetInspector["Dataset Inspector"]
  Webviews --> TrainingLauncher["Training Launcher"]
  Webviews --> ExportWizard["Export Wizard"]
  Webviews --> AnnotationEditor["Annotation Editor"]
  Webviews --> Compare["Run Compare / Timeline"]
  Trees --> Client["Extension Host Client"]
  Status --> Client
  Client --> HTTP["fovux-mcp HTTP"]
  Dashboard --> HTTP
  DatasetInspector --> HTTP
  TrainingLauncher --> HTTP
  ExportWizard --> HTTP
  HTTP --> Health["/health: no auth"]
  HTTP --> Runs["/runs and /runs/:id: auth required"]
  HTTP --> Stream["/runs/:id/stream: SSE, auth required"]
  HTTP --> MetricsAlias["/runs/:id/metrics: compatibility SSE alias"]
  HTTP --> ToolsEndpoint["/tools/:name: auth required, rate-limited"]
  HTTP --> Stdio["MCP stdio transport"]
  ToolsEndpoint --> MCP["fovux-mcp tool registry"]
  Stdio --> MCP
  MCP --> Tools["Dataset / Train / Eval / Export / Infer tools"]
  Tools --> Registry["SQLite RunRegistry"]
  Tools --> Worker["Detached train_worker subprocess"]
  Worker --> Artifacts["FOVUX_HOME runs, weights, metrics.jsonl, exports"]
  Artifacts --> Decorations
```

## Data Flow

1. Studio reads `fovux.home` or `FOVUX_HOME` and starts `fovux-mcp serve --http --tcp` on demand.
2. The extension host uses the short-lived local HTTP client for health, list, detail, and tool
   invocation calls.
3. Webviews receive `baseUrl`, auth token, and initial state from the extension host.
4. Long-lived metric streaming stays in the webview through `/runs/{id}/stream`.
   Older Studio clients can still use `/runs/{id}/metrics`; current clients fall back to polling
   run summaries if SSE is unavailable.
5. Training is launched as a detached subprocess, and the worker writes `metrics.jsonl`,
   `status.json`, weights, and logs under the run directory.

## Security Model

Fovux is local-first and private by default. The HTTP transport binds locally, requires bearer-token
auth for non-health endpoints, and stores the token under `FOVUX_HOME/auth.token`. The Studio
extension reads that token from the same filesystem and never asks the user to paste it into a UI.

The default operating model is intentionally simple:

- no hosted control plane
- no telemetry unless explicitly enabled
- no registry publishing without maintainer approval
- no background CI on Azure or GitLab mirrors

## Run Lifecycle

A normal detection workflow looks like this:

1. `dataset_inspect` validates local YOLO/COCO structure and sample metadata.
2. `train_start` creates a run directory, writes params atomically, and launches
   `python -m fovux.core.train_worker`.
3. The worker updates `metrics.jsonl`, `status.json`, and checkpoint weights.
4. Studio subscribes to `/runs/{id}/stream` and overlays live chart series.
5. `eval_run`, `eval_error_analysis`, and `eval_per_class` diagnose model quality.
6. `export_onnx`, `export_tflite`, and `quantize_int8` produce deployment artifacts.
7. `benchmark_latency` and `quantize_report` help decide whether the artifact is ready.

## Extension Panels

The extension keeps the existing v2 core panel layout:

- Runs tree: training status, stop/resume/delete/tag/copy actions plus Explorer decorations for
  run folder status.
- Models tree: local checkpoints and model library artifacts.
- Exports tree: export history and reveal actions.
- Doctor tree: structured diagnostics with fix commands for backend, server, home, and security
  issues.
- Dashboard: selected run cards, active-run status bar sync, and metric overlays from SSE.
- Dataset Inspector: class distribution, missing-label images, bbox size buckets, and optional
  evaluation-backed confusion data.
- Training Launcher: preset-based guarded training form with user presets, import/export, and
  import-from-run.
- Export Wizard: CPU, GPU, edge, and mobile target guidance for ONNX/TensorRT/TFLite/INT8 flows.
- Annotation Editor: canvas-based YOLO label draw, select, move, resize, delete, undo, and save.

## Workspace Trust

Fovux Studio declares limited support for untrusted workspaces. Read-only views can display local
run, model, export, and diagnostic data. Mutating actions such as starting the backend or launching
training require a trusted workspace and fail before spawning processes when trust is disabled.

## CLI Aliases

The backend intentionally exposes both `fovux-mcp` and `fovux` entry points. `fovux-mcp` is the
primary alias used by Studio and MCP clients; `fovux` is a shorter convenience alias for direct CLI
use.
