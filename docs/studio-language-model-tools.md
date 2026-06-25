# Fovux Studio Language Model Tools

Fovux Studio contributes a curated VS Code Language Model Tool surface for high-value interactive
workflows. The full backend tool surface remains available through the stdio MCP server.

## VS Code LM Tool contract

Every contributed Studio LM tool must have:

- a `fovux_{verb}_{noun}` contribution name;
- a prompt reference name;
- a `displayName`, `userDescription`, and detailed `modelDescription`;
- an object `inputSchema` with parameter descriptions;
- a mapped backend `mcpToolName`, unless it has an explicit Studio-only reason;
- contextual confirmation text from `prepareInvocation`;
- actionable, redacted error messages that do not expose bearer tokens or full private paths.

## Exposed backend tools

The Studio LM surface intentionally exposes dataset inspection/validation, training lifecycle,
evaluation, export, quantization, deployment advice, model profiling, run management, and doctor
workflows. These are the workflows most likely to benefit from VS Code context and human approval.

## Backend tools not directly exposed as Studio LM tools

| Backend tool group | Reason |
| --- | --- |
| Active-learning queue tools | Still experimental and better driven from dedicated Studio views with queue state. |
| Dataset conversion, augmentation, and splitting | File-writing workflows need guided UI previews before broad agent exposure. |
| Support bundle, audit, and policy tools | Administrative/system tools remain available through MCP and Studio panels. |
| Inference and RTSP tools | Runtime-heavy live streams need dedicated webview/session controls. |
| Ensemble and visual comparison tools | Better suited to visual Studio workflows than automatic agent calls. |
| Run archive and MLflow sync | Export/network side effects require a future guided approval workflow. |
| Reproducibility bundle export | Available through MCP; Studio LM exposure should wait for release-evidence UI. |
| Fine-grained evaluation analysis/report tools | Covered by higher-level evaluation and compare tools for LM use. |

This mapping is enforced by:

```bash
python scripts/check_studio_lm_tools.py
```
