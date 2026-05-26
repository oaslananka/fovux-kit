# run_delete

Deletes a non-running training run from the SQLite registry and, by default, removes its run
directory under `FOVUX_HOME/runs`.

## Input schema

| Field          | Type      | Default  | Description                                           |
| -------------- | --------- | -------- | ----------------------------------------------------- |
| `run_id`       | `string`  | required | Run identifier to delete.                             |
| `delete_files` | `boolean` | `true`   | Remove the run directory as well as the registry row. |
| `force`        | `boolean` | `false`  | Allow deletion of a run still marked `running`.       |

## Output schema

| Field              | Type      | Description                            |
| ------------------ | --------- | -------------------------------------- |
| `run_id`           | `string`  | Deleted run identifier.                |
| `deleted_registry` | `boolean` | Whether the registry row was removed.  |
| `deleted_files`    | `boolean` | Whether the run directory was removed. |

## MCP example

```json
{ "run_id": "run_demo", "delete_files": true, "force": false }
```

## HTTP example

```bash
curl -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "content-type: application/json" \
  -d '{"run_id":"run_demo","delete_files":true}' \
  http://127.0.0.1:7823/tools/run_delete
```

## Common failures

- `FOVUX_TRAIN_001`: the run ID does not exist.
- `FOVUX_TRAIN_000`: the run is still running. Stop it first or pass `force=true`.
- `FOVUX_CONFIG_001`: the stored run path escapes `FOVUX_HOME/runs`.

Related tools: `train_stop`, `train_status`, `run_tag`.
