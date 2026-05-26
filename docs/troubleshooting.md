# Troubleshooting

Common issues and their resolutions, organized by error code.

## FOVUX_DATASET_NOT_FOUND

**Symptom:** Tool returns `FovuxDatasetNotFoundError`.

**Cause:** The dataset path does not exist or is not accessible.

**Fix:**
1. Verify the path exists: `ls <dataset_path>/data.yaml`.
2. Ensure `FOVUX_HOME` is set correctly.
3. Check file permissions.

## FOVUX_VALIDATION_ERROR

**Symptom:** Tool returns `FovuxValidationError`.

**Cause:** Input parameters failed validation.

**Fix:**
1. Check the error message for which field is invalid.
2. Verify `data.yaml` is valid YOLO format.
3. Ensure numeric parameters are within documented ranges.

## FOVUX_RUN_NOT_FOUND

**Symptom:** Tool returns `FovuxRunNotFoundError`.

**Cause:** The referenced run ID does not exist in the registry.

**Fix:**
1. List runs with `fovux-mcp serve --http` then `GET /runs`.
2. Check if the run was deleted or the registry was reset.

## HTTP 401 Unauthorized

**Symptom:** Studio or curl returns 401 on authenticated endpoints.

**Cause:** Missing or invalid bearer token.

**Fix:**
1. Check that `FOVUX_HOME/auth.token` exists and is readable.
2. Rotate the token: `fovux-mcp rotate-token`.
3. Restart the server and Studio.

## Server fails to start

**Symptom:** `fovux-mcp serve --http` exits immediately.

**Cause:** Port already in use or missing dependencies.

**Fix:**
1. Check if port 7823 is in use: `lsof -i :7823` (Unix) or `netstat -ano | findstr 7823` (Windows).
2. Run `fovux doctor` to check dependencies.
3. Try a different port: `fovux-mcp serve --http --port 8000`.

## ONNX export fails

**Symptom:** `export_onnx` returns an error about unsupported operations.

**Cause:** Model contains operations not supported by the target ONNX opset.

**Fix:**
1. Check `onnxruntime` version compatibility.
2. Try a simpler model architecture.
3. Check the export error details for the specific unsupported operation.
