# Licensing and Third-party Boundaries

Fovux core code is licensed under Apache-2.0. Optional machine-learning frameworks, models, export
runtimes, hosted services, and deployment targets can carry separate licenses, terms, accounts, or
redistribution obligations.

## Boundary rules

- Fovux core: Apache-2.0, with repository NOTICE files.
- Ultralytics integration: optional runtime dependency; review Ultralytics license/terms before training,
  redistribution, or commercial deployment.
- ONNX, TensorRT, CoreML, OpenVINO, TFLite, NCNN, RKNN, and Edge TPU runtimes: optional export or runtime
  targets; each target may require separate SDKs, platform terms, or hardware vendor tooling.
- W&B and Hugging Face integrations: optional hosted services; users must explicitly configure accounts,
  tokens, and data upload behavior.
- Fovux must not imply that exported artifacts inherit the Fovux Apache-2.0 license.
- Support bundles should include package/version inventory where feasible so users can audit dependencies.

## Studio guidance

Studio must keep optional hosted integrations opt-in, preserve no-telemetry defaults, and surface licensing
or account caveats before enabling third-party services.
