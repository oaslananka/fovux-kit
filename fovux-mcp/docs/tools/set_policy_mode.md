# set_policy_mode

Set the local security policy mode to adjust permissions and confirmation prompts.

## Inputs

- `mode` (string, required): The target security policy mode. Valid options are `safe`, `developer`, `automation`, or `lab`.

## Outputs

- `policy_mode` (string): The newly updated active security policy mode.
- `allowed_tools` (array of strings): List of MCP tools that are allowed to run in the updated mode.
- `requires_confirmation` (object): Map showing which tools require user confirmation.
- `scopes_enforced` (boolean): Flag indicating whether directory scope constraints are currently being enforced.

## Examples

```json
{
  "mode": "safe"
}
```

## Common Errors

- `ValueError`: Raised if an invalid policy mode is supplied (valid options: `safe`, `developer`, `automation`, `lab`).

## Related Tools

`get_policy_status`
