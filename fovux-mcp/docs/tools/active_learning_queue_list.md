# active_learning_queue_list

List review queue entries from the SQLite database.

## Inputs

- `dataset_path`: Optional path to filter by target dataset.
- `status`: Status to filter by (`pending`, `reviewed`, `skipped`).
- `limit`: Maximum number of entries to return.

## Outputs

- `queue_entries`: List of matching review queue items.

## Examples

```json
{
  "status": "pending",
  "limit": 100
}
```
