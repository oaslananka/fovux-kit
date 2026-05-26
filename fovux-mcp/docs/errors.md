# Errors

Fovux surfaces only `FovuxError` subclasses at tool boundaries.

## Common Codes

- `FOVUX_DATASET_001`: dataset path not found
- `FOVUX_DATASET_002`: malformed or unsupported dataset format
- `FOVUX_DATASET_003`: dataset contains zero images
- `FOVUX_TRAIN_001`: run not found
- `FOVUX_EVAL_001`: checkpoint not found
- `FOVUX_INFER_001`: RTSP connection failed
- `FOVUX_CONFIG_001`: path validation failed

## Error Shape

Each error includes:

- a stable code
- a short human-readable message
- an optional remediation hint

## Debugging Tip

Set `FOVUX_LOG_FORMAT=json` and `FOVUX_LOG_LEVEL=DEBUG` when reproducing tool failures from the CLI or HTTP transport.
