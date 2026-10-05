# Agent Workflow Reference

Authoritative local workflow commands for human contributors and automation.
All commands are verified against `Taskfile.yml` and `required-local-gates.json`.

## Prerequisites

| Tool         | Version                               | Install                                                         |
| ------------ | ------------------------------------- | --------------------------------------------------------------- |
| Python       | ≥ 3.12                                | https://python.org                                              |
| uv           | latest                                | official standalone installer                                   |
| Node.js      | ≥ 22.0.0 (24.16.0 pinned in `.nvmrc`) | https://nodejs.org                                              |
| pnpm         | 10.34.1                               | `corepack enable && corepack prepare pnpm@10.34.1 --activate`   |
| pre-commit   | ≥ 4.0                                 | included in `dev` extra                                         |
| go-task/task | 3.50.0                                | `go install github.com/go-task/task/v3/cmd/task@v3.50.0`        |
| actionlint   | 1.7.12                                | `go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.12` |
| gitleaks     | 8.30.1                                | `go install github.com/zricethezav/gitleaks/v8@v8.30.1`         |
| OSV-Scanner  | 2.3.8                                 | installed by `scripts/bootstrap-dev.sh`                         |
| Trivy        | 0.70.0                                | installed by `scripts/bootstrap-dev.sh`                         |

## Setup

```bash
# Install all dev dependencies
task install
```

Equivalent per-component commands:

- `cd fovux-mcp && uv sync --frozen --extra dev`
- `corepack pnpm@10.34.1 --ignore-workspace --version`
- `cd fovux-studio && corepack pnpm@10.34.1 --ignore-workspace install --frozen-lockfile`
- `cd fovux-mcp-npm && npm ci --ignore-scripts`

```bash
# Install git hooks
task hooks
```

## Format

```bash
# Auto-format the codebase
task format
```

Individual commands:

- `cd fovux-mcp && uv run ruff check --fix .`
- `cd fovux-mcp && uv run ruff format .`
- `cd fovux-studio && corepack pnpm@10.34.1 --ignore-workspace prettier --write --ignore-path ../.prettierignore .`
- `cd fovux-studio && corepack pnpm@10.34.1 --ignore-workspace prettier --write --ignore-path ../.prettierignore ../fovux-mcp-npm`

## Lint (read-only)

```bash
# Run all linters (read-only)
task lint
```

Individual commands:

- `cd fovux-mcp && uv run ruff check .`
- `cd fovux-mcp && uv run ruff format --check .`
- `cd fovux-studio && corepack pnpm@10.34.1 --ignore-workspace run lint`
- `cd fovux-studio && corepack pnpm@10.34.1 --ignore-workspace prettier --check --ignore-path ../.prettierignore ../fovux-mcp-npm`
- `node --check fovux-mcp-npm/bin/fovux-mcp.js`
- `actionlint`
- `uvx zizmor==1.27.0 --pedantic --min-severity=high .github/workflows`

## Type-check

```bash
# Static type checking
task typecheck
```

Individual commands:

- `cd fovux-mcp && uv run mypy --strict --warn-unused-ignores src/fovux`
- `cd fovux-studio && corepack pnpm@10.34.1 --ignore-workspace run typecheck`

## Test

```bash
# Run unit tests
task test
```

```bash
# Run only fast tests (exclude slow, integration, network, gpu, security, chaos, benchmark)
task test:fast
```

```bash
# Run tests with coverage
task test:cov
```

Individual commands:

- `cd fovux-mcp && uv run pytest --basetemp="${TMPDIR:-/tmp}/fovux-kit-pytest" --cov=fovux --cov-fail-under=85 --cov-report=term-missing --cov-report=html --cov-report=xml`
- `cd fovux-studio && corepack pnpm@10.34.1 --ignore-workspace run coverage:ci`

## Security

```bash
# Run credential-free developer security scans
task security:developer
```

```bash
# Run all security scans (includes pip-audit, pnpm-audit, npm-audit, gitleaks)
task security
```

```bash
# Run the strict repository posture check (credential-aware)
task security:posture
```

Individual security tasks:

- `task security:semgrep` — validate and run pinned repository-owned Semgrep rules
- `task security:trivy` — run the pinned-policy credential-free Trivy filesystem scan (`python scripts/run_trivy.py --required`)
- `task security:osv` — run the credential-free OSV lockfile vulnerability scan (`python scripts/run_osv.py --required`)
- `task security:bandit` — run the backend Bandit security scan (`cd fovux-mcp && uv run bandit -r src/fovux -ll`)
- `task security:pip-audit` — audit exported backend runtime dependencies
- `task security:pnpm-audit` — audit Studio production dependencies
- `task security:npm-audit` — audit npm wrapper production dependencies
- `task security:gitleaks` — run the required repository Gitleaks scan (`python scripts/run_gitleaks.py --required`)

### Hosted-only required checks (from `required-local-gates.json`)

These checks run only in CI and have no credential-free local equivalent:

| Context                  | Reason                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------- |
| `compatibility-required` | Three-OS by three-Python compatibility matrix not repeated locally                                      |
| `node-required`          | Node 22 and 24 compatibility matrix is a hosted runtime boundary                                        |
| `posture`                | Strict posture job reads GitHub ruleset, code-scanning, and Dependabot state via repository-scoped APIs |
| `codeql-required`        | GitHub-hosted CodeQL analysis and SARIF processing                                                      |
| `dependency-review`      | GitHub Dependency Review requires PR dependency metadata                                                |
| `scorecard-required`     | OpenSSF Scorecard relies on hosted repository and workflow metadata                                     |

## PR Rules

- Linear history required
- Required checks: `ci-required`, `security-required`, `dependency-review`, `codeql-required`, `elevated-review-required`
- All review threads must be resolved
- Never weaken gates
- PR-first integration; no target-repo write credentials for workers
- Deterministic formatters preferred over AI edits for formatting-only changes

## Aggregate Gates

```bash
# Run the deterministic primary quality lane locally (install + lint + typecheck + test:cov + security + docs + build + release:dry-run)
task ci
```

```bash
# Run every deterministic credential-free required local gate (ci + deps:renovate:validate + security:developer)
task verify:required
```

## Other Useful Tasks

```bash
# Build distributable packages
task build
```

```bash
# Validate Renovate configuration
task deps:renovate:validate
```

```bash
# Generate Studio LM tool artifacts
task studio:lm-tools:generate
task studio:lm-tools:check
```

```bash
# Validate Studio E2E contracts
task studio:e2e:check
task studio:e2e
```

```bash
# Build and lint documentation
task docs
```

```bash
# Pre-push hook equivalent (typecheck + fast tests + workflow lint)
task pre-push
```

```bash
# Clean build artifacts and caches
task clean
```

## Fast Local Validation

For quick iteration before pushing:

```bash
task typecheck
task test:fast
actionlint
uvx zizmor==1.27.0 --pedantic --min-severity=high .github/workflows
```

Full local gate before requesting merge:

```bash
task verify:required
```
