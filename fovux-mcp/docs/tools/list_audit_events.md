# list_audit_events

Retrieve audit event logs from the local database.

## Inputs

- `limit` (integer, optional): Maximum number of audit events to return. Defaults to 100.
- `offset` (integer, optional): Number of audit events to skip for pagination. Defaults to 0.

## Outputs

- `events` (array of objects): List of audit event records, with each record containing the event `id`, `actor`, `action`, target `entity_type`/`entity_id`, timestamp `created_at`, and details `details`.

## Examples

```json
{
  "limit": 10
}
```

## Common Errors

- Generally does not raise errors; returns empty list if no audit logs are found.

## Related Tools

`get_policy_status`
