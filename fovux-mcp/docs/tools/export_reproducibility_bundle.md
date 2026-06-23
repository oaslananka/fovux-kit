# export_reproducibility_bundle

Export a reproducibility bundle zip file for a training run.

## Inputs

- `run_id` (string, required): The unique identifier of the training run to export.
- `destination_path` (string, optional): The target file path where the reproducibility bundle zip should be saved. If not provided, saves to the run's directory.

## Outputs

- `bundle_path` (string): The absolute path of the generated ZIP bundle.
- `size_bytes` (integer): The size of the generated ZIP bundle in bytes.
- `manifest` (object): Metadata manifest containing run status, hyperparameter configuration, package versions, redacted environment parameters, and metric logs.

## Examples

```json
{
  "run_id": "run_01j1vwbc78"
}
```

## Common Errors

- `FovuxError`: Raised if the specified run ID is not found in the registry.

## Related Tools

`generate_support_bundle`, `run_archive`, `train_status`
