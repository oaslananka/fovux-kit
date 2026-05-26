# Development

## One-time setup

```bash
# Install Task: https://taskfile.dev/installation/
task install     # install dev deps
task hooks       # install git hooks
```

## Daily workflow

```bash
task format      # auto-format
task lint        # check formatting and linting
task typecheck   # static types
task test        # run tests
task ci          # run the full CI pipeline locally
```

## Before push

`pre-push` hook automatically runs `task pre-push`.
If you want to be sure CI will pass:

```bash
task ci          # full local parity with CI
task ci:act      # optional: run GitHub Actions in Docker locally
```

## Troubleshooting

- `task: command not found`: install Task with `brew install go-task` or download from https://taskfile.dev/installation/
- pre-commit hook is too slow: run `pre-commit run --all-files` once to warm caches
- `task ci` fails but CI passes, or vice versa: likely Doppler secrets differ; run `task doppler:check`

```bash
# https://github.com/nektos/act
brew install act    # or download from releases
act -j test         # run the test job locally in Docker
act --list          # see all jobs across all workflows
```
