# sync_to_mlflow

Sync a training run to a local or remote MLflow tracking server.

## Overview

`sync_to_mlflow` reads the metrics, parameters, and artifacts from a Fovux training run and creates a corresponding MLflow run entry. Requires an accessible MLflow tracking server.

## Input Schema

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `run_id` | `string` | Yes | — | Fovux run ID to sync. |
| `tracking_uri` | `string` | No | `"http://localhost:5000"` | MLflow tracking server URI. |
| `experiment_name` | `string` | No | `"fovux"` | MLflow experiment name. |

## Output Schema

| Field | Type | Description |
|---|---|---|
| `run_id` | `string` | Fovux run ID. |
| `mlflow_run_id` | `string` | Created MLflow run ID. |
| `tracking_uri` | `string` | MLflow server URI used. |
| `experiment_name` | `string` | MLflow experiment name. |
| `synced_metrics` | `integer` | Number of metric entries synced. |

## Examples

### CLI
```bash
curl -X POST http://127.0.0.1:7823/tools/sync_to_mlflow \
  -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "Content-Type: application/json" \
  -d '{"run_id": "abc123", "tracking_uri": "http://localhost:5000"}'
```

### Python
```python
from fovux.tools.sync_to_mlflow import sync_to_mlflow
result = sync_to_mlflow("abc123", tracking_uri="http://localhost:5000")
```

## Notes & Limits

- Requires the `mlflow` Python package to be installed.
- Network connectivity to the MLflow server is required.
- This tool is the only Fovux tool that makes external network requests.

## Failure Modes

- `ImportError` if `mlflow` is not installed.
- Connection errors if the MLflow server is unreachable.
- `FovuxRunNotFoundError` if the run ID is not in the registry.
