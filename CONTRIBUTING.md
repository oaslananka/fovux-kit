# Contributing to Fovux

Thank you for your interest in improving Fovux. This document describes how to
set up a local development environment, run the quality gates, and submit changes.

## Repository layout

```
fovux/
├── fovux-mcp/        Python MCP server (uv, hatchling, FastMCP)
├── fovux-studio/     VS Code extension (TypeScript, React, tsup)
├── scripts/          Repo-wide tooling (quality_gate.py, build_spdx_sbom.py …)
├── docs/             Architecture and operations notes
└── examples/         Curl-based quickstart recipes
```

## Prerequisites

| Tool                             | Version                                                       | Install                                                       |
| -------------------------------- | ------------------------------------------------------------- | ------------------------------------------------------------- |
| Python                           | ≥ 3.11                                                        | https://python.org                                            |
| [uv](https://docs.astral.sh/uv/) | latest                                                        | official standalone installer                                 |
| Node.js                          | >= 22.0.0, with 24.14.1 pinned in `.nvmrc` for release builds | https://nodejs.org                                            |
| pnpm                             | 10.33.0                                                       | `corepack enable && corepack prepare pnpm@10.33.0 --activate` |
| pre-commit                       | ≥ 4.0                                                         | included in `dev` extra                                       |

## Local setup

```bash
git clone https://github.com/oaslananka/fovux
cd fovux

# Fast path: install dependencies, hooks, and run the repo-quality gate.
task install
task hooks
task ci
```

That sequence is the expected 15-minute path to a working checkout. If `task` is unavailable,
run the Python and Studio commands below directly.

## Running the quality gates

### Python (fovux-mcp)

```bash
cd fovux-mcp

# Lint + type-check + test (mirrors CI)
python ../scripts/quality_gate.py mcp-check

# Or run each step individually
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest --cov=fovux --cov-fail-under=92
```

### TypeScript (fovux-studio)

```bash
cd fovux-studio

# Full check (format + lint + typecheck + test + build + audit)
pnpm verify

# Or individually
pnpm format
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

## CLI aliases

The backend publishes two command aliases on purpose:

- `fovux-mcp` is the primary alias used by VS Code Studio, MCP clients, examples, and automation.
- `fovux` is a shorter convenience alias for direct CLI use.

Keep both aliases working when changing CLI registration, documentation, or release scripts.

## Optional Doppler setup

Normal local development does not require Doppler. Release workflows that publish artifacts do
require the Doppler CLI and a `DOPPLER_TOKEN` secret because release signing and publishing commands
run through `doppler run --project all --config main`. See `docs/doppler-setup.md` for maintainer
setup and troubleshooting.

## Commit style

Fovux uses [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(mcp): add quantize_fp16 tool
fix(studio): declare fovux.revealPath in package.json
docs: update tool count in README
ci: pin actions/checkout to SHA
chore(mcp): remove dead log_level no-op in config.py
```

The pre-push hook runs the full quality gate. Do not skip it with `--no-verify`.

## Submitting a pull request

1. Fork the repo and create a branch from `main`.
2. Make your changes with appropriate tests.
3. Ensure `python scripts/quality_gate.py repo-check` passes locally.
4. Open a pull request against `main` in `oaslananka/fovux` (the canonical repo).
5. Fill in the pull request template.

## Branch / remote model

- `oaslananka/fovux` — canonical public repo; submit PRs here.
- `oaslananka-lab/fovux` — CI mirror; do not submit PRs here.

See [docs/repository-operations.md](docs/repository-operations.md) for the full
multi-remote model.

## Reporting bugs

Use the GitHub issue templates. For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions are licensed under the
[Apache-2.0 license](LICENSE). See [NOTICE](NOTICE) for third-party acknowledgements.
