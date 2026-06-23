# get_policy_status

Retrieve the current security policy status and allowed tools for the active environment.

## Inputs

This tool takes no arguments.

## Outputs

- `policy_mode` (string): The active security policy mode (e.g. `safe`, `developer`, `automation`, or `lab`).
- `allowed_tools` (array of strings): List of MCP tools that are allowed to run in the current mode.
- `requires_confirmation` (object): Map showing which tools require explicit user confirmation before running.
- `scopes_enforced` (boolean): Flag indicating whether directory scope constraints are currently being enforced.

## Examples

```json
{}
```

## Common Errors

- Generally does not raise errors; returns the default policy if not explicitly configured.

## Related Tools

`set_policy_mode`
