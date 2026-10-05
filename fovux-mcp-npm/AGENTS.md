# npm Wrapper Instructions

These instructions apply to `fovux-mcp-npm/**` and supplement the root instructions.

This package is a thin launcher/delegation surface for the Python `fovux-mcp` package. It must not become an independent implementation of Fovux behavior.

## Delegation contract

- Preserve explicit version/compatibility behavior between the npm wrapper and Python package.
- Delegate through the reviewed `uvx`/Python launch path; do not shell-interpolate user-controlled arguments.
- Forward arguments and exit status predictably.
- Do not embed credentials, telemetry, download scripts or hidden network behavior.
- Keep install/runtime behavior minimal and auditable.

## Release

Package metadata, README examples, supported Node versions and release version mapping must match the repository release contract. Publishing occurs only through protected workflows.

## Verification

Run syntax checks, npm audit, `npm pack --dry-run`, and wrapper compatibility/smoke tests when launcher behavior or package contents change.
