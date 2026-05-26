# CI Skip Policy

## When macOS/Windows jobs can be skipped

To conserve CI minutes, macOS and Windows matrix entries run only on:
- Push to `main`
- Pull request with `[ci-all]` in the commit message

All other pushes and PRs run only the Ubuntu matrix.

## How to invoke full matrix manually

Add `[ci-all]` or `[full-matrix]` to your commit message:

```
fix: resolve path separator issue [ci-all]
```

## Workflow skip via `paths`

All workflows use `paths` filters to skip jobs that don't affect the
relevant package:

| Workflow | Triggers on changes to |
|---|---|
| `mcp` job | `fovux-mcp/**`, `scripts/**`, `pyproject.toml` |
| `studio` job | `fovux-studio/**` |
| `docs-deploy` | `fovux-mcp/docs/**`, `fovux-mcp/mkdocs.yml` |
| `sync-labels` | `.github/labels.yml` |

## Emergency override

Use `workflow_dispatch` to manually trigger any workflow regardless
of path filters.
