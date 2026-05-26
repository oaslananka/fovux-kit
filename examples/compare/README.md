# Compare Runs Example

Use this recipe after creating at least two runs:

```bash
curl -H "Authorization: Bearer $(cat ~/.fovux/auth.token)" \
  -H "content-type: application/json" \
  -d '{"run_ids":["run_a","run_b"]}' \
  http://127.0.0.1:7823/tools/run_compare
```

Fovux writes a Markdown report and PNG chart under `FOVUX_HOME/exports`, and
Studio can open the comparison webview for side-by-side inspection.
