# run_tag

Replaces the tag list for a training run. Tags are stored in the local SQLite registry and used by
Studio filtering/search workflows.

## Input schema

| Field    | Type       | Default  | Description                                      |
| -------- | ---------- | -------- | ------------------------------------------------ |
| `run_id` | `string`   | required | Run identifier to update.                        |
| `tags`   | `string[]` | `[]`     | Replacement tag list. Empty strings are ignored. |

## Output schema

| Field    | Type       | Description                  |
| -------- | ---------- | ---------------------------- |
| `run_id` | `string`   | Updated run identifier.      |
| `tags`   | `string[]` | Normalized, sorted tag list. |

## MCP example

```json
{ "run_id": "run_demo", "tags": ["baseline", "edge"] }
```

## HTTP example

```bash
curl -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "content-type: application/json" \
  -d '{"run_id":"run_demo","tags":["baseline","edge"]}' \
  http://127.0.0.1:7823/tools/run_tag
```

## Common failures

- `FOVUX_TRAIN_001`: the run ID does not exist.

Related tools: `run_delete`, `run_compare`, `train_status`.
