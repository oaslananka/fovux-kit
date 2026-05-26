# train_adjust

Adjust hyperparameters of a running training run.

## Overview

`train_adjust` writes updated hyperparameter values to a running training run's configuration. The training worker picks up the changes at the start of the next epoch.

## Input Schema

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `run_id` | `string` | Yes | — | ID of the running training run. |
| `lr` | `float` | No | `null` | New learning rate. |
| `batch` | `integer` | No | `null` | New batch size. |
| `epochs` | `integer` | No | `null` | New total epoch count. |

## Output Schema

| Field | Type | Description |
|---|---|---|
| `run_id` | `string` | Run ID. |
| `adjusted` | `object` | Map of adjusted parameter names to their new values. |
| `status` | `string` | Current run status. |

## Examples

### CLI
```bash
curl -X POST http://127.0.0.1:7823/tools/train_adjust \
  -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "Content-Type: application/json" \
  -d '{"run_id": "abc123", "lr": 0.001, "epochs": 200}'
```

### Python
```python
from fovux.tools.train_adjust import train_adjust
result = train_adjust("abc123", lr=0.001, epochs=200)
```

## Notes & Limits

- Only running or paused runs can be adjusted.
- Changes take effect at the next epoch boundary, not immediately.
- Not all hyperparameters may be adjustable depending on the training backend.

## Failure Modes

- `FovuxRunNotFoundError` if the run ID is not found.
- `FovuxValidationError` if the run is not in a running state.
