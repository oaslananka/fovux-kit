# Fovux Studio Instructions

These instructions apply to `fovux-studio/**` and supplement the root instructions.

## Boundary

Fovux Studio is the VS Code companion. It connects to the trusted local Fovux backend, renders local run/dataset/model state, exposes guarded workflows and packages the Marketplace/Open VSX extension.

## Trust and local API

- Do not spawn an arbitrary backend executable or connect to arbitrary remote endpoints without an explicit design.
- Keep the local server/token discovery contract aligned with backend compatibility docs.
- Treat API responses, project files, dataset metadata, paths and model/run content as untrusted before rendering or using them in commands.
- State-changing workflows must preserve workspace-trust and backend challenge/confirmation semantics where applicable.
- Do not bypass backend tool policy by adding direct filesystem/process mutations in the extension merely for convenience.

## Webviews

- Preserve restrictive CSP/nonces and escape untrusted text.
- Do not add `eval`, `new Function`, arbitrary remote scripts or broad local resource access.
- Keep message schemas narrow and validate webview-to-extension requests.
- Avoid embedding raw private file contents/paths in diagnostics or telemetry.

## Generated LM tools and guided workflows

Generated Studio language-model tool artifacts are derived from the backend tool schema.

- Change the canonical backend/tool metadata and generator, then regenerate.
- Do not hand-edit generated LM tool definitions to drift from backend policy.
- Guided workflow, train preflight, export target and dataset-intelligence contracts must remain aligned with checked docs and tests.

## Packaging

- `.vscodeignore`, package contents, activation/command contributions, generated assets and release evidence must remain deterministic.
- Do not include repository-only secrets, fixtures, dev artifacts or internal governance files in the VSIX.
- Marketplace claims/screenshots must represent real shipped behavior.

## Verification

Run Studio lint/typecheck/test/coverage/build plus packaged-VSIX e2e contract checks for packaging or end-to-end workflow changes.
