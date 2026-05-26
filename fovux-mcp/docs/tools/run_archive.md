# run_archive

Archive a completed training run to a compressed file.

## Overview

`run_archive` compresses a completed training run directory into a `.tar.gz` archive for storage or transfer. The original run directory is preserved.

## Input Schema

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `run_id` | `string` | Yes | — | ID of the run to archive. |
| `output_path` | `string` | No | `null` | Path for the output archive. Defaults to `<run_path>.tar.gz`. |

## Output Schema

| Field | Type | Description |
|---|---|---|
| `run_id` | `string` | Archived run ID. |
| `archive_path` | `string` | Path to the created archive. |
| `size_bytes` | `integer` | Archive file size. |

## Examples

### CLI
```bash
curl -X POST http://127.0.0.1:7823/tools/run_archive \
  -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "Content-Type: application/json" \
  -d '{"run_id": "abc123"}'
```

### Python
```python
from fovux.tools.run_archive import run_archive
result = run_archive("abc123", output_path="/backups/abc123.tar.gz")
```

## Notes & Limits

- Only completed or failed runs can be archived; running runs are rejected.
- The run directory must exist on disk.

## Failure Modes

- `FovuxRunNotFoundError` if the run ID is not in the registry.
- `FovuxValidationError` if the run is still active.
