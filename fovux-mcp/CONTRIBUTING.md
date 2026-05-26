# Contributing to Fovux MCP

Thank you for your interest in contributing to Fovux! This document explains how to get started.

## Development setup

```bash
# Clone and install with locked dev dependencies
git clone https://github.com/oaslananka/fovux
cd fovux
uv sync --project fovux-mcp --frozen --extra dev

# Node.js / pnpm for the Studio companion
corepack enable
corepack prepare pnpm@10.33.0 --activate
cd fovux-studio
pnpm install --frozen-lockfile
cd ..

# Install the repo-wide git hooks
uv run --project fovux-mcp pre-commit install --hook-type pre-commit --hook-type pre-push
```

## Running tests

```bash
python scripts/quality_gate.py repo-check   # local counterpart of the core CI checks
python scripts/quality_gate.py repo-verify  # adds docs, build, and audit validation

cd fovux-mcp
make test          # run full backend test suite with coverage
make test-unit     # backend unit tests only (fast)
make test-int      # backend integration tests
make lint          # uv lock check + ruff + mypy

cd ../fovux-studio
pnpm check         # lint + typecheck + tests
pnpm verify        # check + build + prod audit
```

## Branch and PR conventions

- Base all PRs on `main`
- Branch names: `feat/…`, `fix/…`, `docs/…`, `chore/…`
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(tools): add dataset_validate`
- PRs must be ≤1500 LOC diff (excluding tests and lock files)
- Every PR must have green CI before merge

## Code style

- `ruff` for linting and formatting (line length 100)
- `mypy --strict` must pass
- All public functions must have type hints and docstrings (Google style)
- Use `pathlib.Path` for all file paths
- No `shell=True` without a `# noqa: S602` comment and justification

## Testing requirements

Every new tool must have:

- At least 3 unit tests
- At least 1 integration test using the fixture data in `tests/fixtures/`
- Coverage ≥85% for the new module

## Adding a new tool

1. Create `src/fovux/tools/<tool_name>.py`
2. Add input/output schemas to `src/fovux/schemas/`
3. Register with `@mcp.tool()` in `src/fovux/server.py`
4. Add unit tests to `tests/unit/tools/test_<tool_name>.py`
5. Add integration test to `tests/integration/`
6. Document in `docs/tools/`

## Reporting issues

Use the GitHub issue templates. For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
