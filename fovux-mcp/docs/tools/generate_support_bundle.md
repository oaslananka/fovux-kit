# generate_support_bundle

Generate a redacted support bundle zip file containing system diagnostic information.

## Inputs

- `destination_path` (string, optional): The target file path where the support bundle zip should be saved. If not provided, saves to a temporary zip file under the Fovux home directory.

## Outputs

- `bundle_path` (string): The absolute path of the generated ZIP bundle.
- `size_bytes` (integer): The size of the generated ZIP bundle in bytes.
- `manifest` (object): System diagnostics including redacted config, host OS summary, package versions, doctor health report, and failed operations.

## Examples

```json
{}
```

## Common Errors

- Errors collecting diagnostics are captured inside the manifest instead of raising a hard exception.

## Related Tools

`export_reproducibility_bundle`, `fovux_doctor`
