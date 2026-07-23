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

| Tool                             | Version                                                       | Install                                                         |
| -------------------------------- | ------------------------------------------------------------- | --------------------------------------------------------------- |
| Python                           | ≥ 3.12                                                        | https://python.org                                              |
| [uv](https://docs.astral.sh/uv/) | latest                                                        | official standalone installer                                   |
| Node.js                          | >= 22.0.0, with 24.16.0 pinned in `.nvmrc` for release builds | https://nodejs.org                                              |
| pnpm                             | 10.34.1                                                       | `corepack enable && corepack prepare pnpm@10.34.1 --activate`   |
| pre-commit                       | ≥ 4.0                                                         | included in `dev` extra                                         |
| go-task/task                     | 3.50.0                                                        | `go install github.com/go-task/task/v3/cmd/task@v3.50.0`        |
| actionlint                       | 1.7.12                                                        | `go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.12` |
| gitleaks                         | 8.30.1                                                        | `go install github.com/zricethezav/gitleaks/v8@v8.30.1`         |
| OSV-Scanner                      | 2.3.8                                                         | installed by `scripts/bootstrap-dev.sh`                         |
| Trivy                            | 0.70.0                                                        | installed by `scripts/bootstrap-dev.sh`                         |

## Local setup

```bash
git clone https://github.com/oaslananka/fovux-kit
cd fovux-kit

# Fast path: install the toolchain/dependencies/hooks and run required local gates.
scripts/bootstrap-dev.sh --install-deps --hooks
task verify:required
```

That sequence is the expected path to a working checkout on Linux/macOS. On Windows, follow the
PowerShell commands in [docs/development.md](docs/development.md). If `task` is unavailable, use the
fallback command blocks in that same page.

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

### Generated Studio Language Model tools

The backend schema snapshot is canonical for Studio LM input schemas and policy metadata. Edit
`fovux-studio/src/fovux/tools/overrides.json` only for Studio-specific names, descriptions, tags,
prompt references, and custom confirmation copy. Then regenerate and verify the committed artifacts:

```bash
task studio:lm-tools:generate
task studio:lm-tools:check
```

Do not edit `fovux-studio/src/fovux/tools/definitions.ts` or the granular
`contributes.languageModelTools` entries in `fovux-studio/package.json` by hand.

## CLI aliases

The backend publishes two command aliases on purpose:

- `fovux-mcp` is the primary alias used by VS Code Studio, MCP clients, examples, and automation.
- `fovux` is a shorter convenience alias for direct CLI use.

Keep both aliases working when changing CLI registration, documentation, or release scripts.

## Environment and publishing credentials

Copy the variable names from `.env.example` into an untracked `.env` file when local overrides are
needed. Publishing credentials are stored as protected GitHub Actions secrets and are never required
for normal local development.

## Commit style

Fovux uses [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(mcp): add quantize_fp16 tool
fix(studio): declare fovux.revealPath in package.json
docs: update tool count in README
ci: pin actions/checkout to SHA
chore(mcp): remove dead log_level no-op in config.py
```

The pre-push hook runs fast type, test, workflow, and OSV checks. Do not skip it with
`--no-verify`; run `task verify:required` before requesting merge.

## Submitting a pull request

1. Fork the repo and create a branch from `main`.
2. Make your changes with appropriate tests.
3. Ensure `python scripts/quality_gate.py repo-check` passes locally; run `task docs` for documentation-only changes and `task verify:required` before larger PRs.
4. Open a pull request against `main` in `oaslananka/fovux-kit` (the canonical repo).
5. Fill in the pull request template.

## Branch / remote model

- `oaslananka/fovux-kit` — canonical public repo; submit PRs here.

See [docs/repository-operations.md](docs/repository-operations.md) for the full
multi-remote model.

## Reporting bugs

Use the GitHub issue templates. For security vulnerabilities, see [SECURITY.md](SECURITY.md).

## License

By contributing, you agree that your contributions are licensed under the
[Apache-2.0 license](LICENSE). See [NOTICE](NOTICE) for third-party acknowledgements.
