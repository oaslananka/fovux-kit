# Development

This page is the canonical local developer workflow for the monorepo.

## Required toolchain

| Tool | Pinned / supported version | Purpose |
| --- | --- | --- |
| Python | 3.12, 3.13, or 3.14 | Backend runtime and tests |
| `uv` | latest stable | Python dependency, build, and audit workflow |
| Node.js | >=22.0.0; `.nvmrc` pins 24.16.0 for release builds | Studio and npm-wrapper runtime |
| pnpm | 10.34.1 | Studio package manager |
| Go | latest stable | Installs local CI helper binaries |
| go-task/task | 3.50.0 | Monorepo task runner |
| actionlint | 1.7.12 | GitHub Actions linting |
| gitleaks | 8.30.1 | Secret scanning |
| Renovate CLI | 43.272.4, Node.js >=24.11 | Optional full schema validation |
| Semgrep | 1.170.0 | Repository-owned local and CI SAST rules |
| Snyk CLI | optional | Authenticated maintainer dependency/code scans |
| SonarScanner | optional | Explicit authenticated branch or PR analysis |
| act | optional | Local GitHub Actions simulation |

## One-time bootstrap

### Linux / macOS

```bash
git clone https://github.com/oaslananka/fovux-kit
cd fovux-kit
scripts/bootstrap-dev.sh --install-deps --hooks
```

The script verifies Python, Node, npm, Go, `uv`, Task, actionlint, gitleaks, and pnpm. It installs
Task/actionlint/gitleaks through `go install` when missing and enables `pnpm@10.34.1` through
Corepack.

### Windows PowerShell

```powershell
git clone https://github.com/oaslananka/fovux-kit
cd fovux-kit
corepack enable
corepack prepare pnpm@10.34.1 --activate
go install github.com/go-task/task/v3/cmd/task@v3.50.0
go install github.com/rhysd/actionlint/cmd/actionlint@v1.7.12
go install github.com/zricethezav/gitleaks/v8@v8.30.1
$env:Path = "$(go env GOPATH)\bin;$env:Path"
task install
task hooks
```

Install `uv` from the official Astral documentation before running `task install` when it is not
already available.

## Daily workflow with Task

```bash
task install     # install Python, Studio, and npm-wrapper dependencies
task format      # auto-format
task lint        # lint Python, Studio, npm wrapper, and workflows
task typecheck   # static typing
task test        # backend and Studio tests
task security    # Bandit, pip-audit, pnpm audit, npm audit, gitleaks, security posture
task deps:renovate:validate  # static policy and Renovate schema validation
task security:semgrep        # repository Semgrep fixtures and production scan
task security:snyk           # optional Snyk scan; explicit SKIP without local config
task security:sonar -- --branch feature/name  # optional Sonar analysis
task docs        # version/tool/docs truth checks, MkDocs strict build, docs code-block lint
task build       # Python package, Studio bundle, npm wrapper dry-run pack
task ci          # full local parity with the main CI workflow
task ci:act      # optional GitHub Actions simulation through Docker/act
```

## Direct fallback commands without Task

Use these when a machine cannot install Task. They mirror the main task groups.

### Install

```bash
cd fovux-mcp && uv sync --frozen --extra dev
cd ../fovux-studio && corepack pnpm@10.34.1 --ignore-workspace install --frozen-lockfile
cd ../fovux-mcp-npm && npm ci --ignore-scripts
```

### Lint

```bash
cd fovux-mcp && uv run ruff check . && uv run ruff format --check .
cd ../fovux-studio && corepack pnpm@10.34.1 --ignore-workspace run lint
cd .. && node --check fovux-mcp-npm/bin/fovux-mcp.js
actionlint
```

### Typecheck

```bash
cd fovux-mcp && uv run mypy --strict --warn-unused-ignores src/fovux
cd ../fovux-studio && corepack pnpm@10.34.1 --ignore-workspace run typecheck
```

### Test

```bash
cd fovux-mcp && uv run pytest -x --no-header -q --basetemp="${TMPDIR:-/tmp}/fovux-kit-pytest"
cd ../fovux-studio && corepack pnpm@10.34.1 --ignore-workspace test --run
```

### Security

```bash
cd fovux-mcp
uv run bandit -r src/fovux -ll
uv export --no-dev --no-editable --no-emit-project --no-hashes --output-file requirements-audit.txt
uv run pip-audit --requirement requirements-audit.txt
cd ../fovux-studio && corepack pnpm@10.34.1 --ignore-workspace audit --prod
cd ../fovux-mcp-npm && npm audit --omit=dev
cd .. && gitleaks detect --no-banner --redact
python scripts/generate_security_posture.py
```

### Developer security scanners

```bash
task security:semgrep
task security:snyk
SNYK_TOKEN=... task security:snyk
SONAR_TOKEN=... task security:sonar -- --branch feature/security
SONAR_TOKEN=... task security:sonar -- --pull-request 138 --branch feature/security --base main
```

Semgrep is deterministic and runs in normal pre-commit plus the required security workflow. Snyk
runs at pre-push/manual through `scripts/run_snyk.py`; missing CLI or `SNYK_TOKEN` produces an
explicit local `SKIP`, while `--required` converts missing configuration to a failure. Sonar is
manual-only because it uploads repository-wide analysis state. `scripts/run_sonar.py` uses the
current git branch when `--branch` is omitted and never places `SONAR_TOKEN` on the command line.
Hosted Snyk and SonarQube Cloud pull-request checks remain the authoritative cloud results.

See [developer-security.md](developer-security.md) for installation, credentials, and failure
semantics.

### Dependency automation

```bash
python scripts/validate_renovate_config.py
npm exec --yes --package=renovate@43.272.4 -- renovate-config-validator renovate.json
```

The full schema validator requires Node.js 24.11 or newer. Use the `.nvmrc` runtime before running
the second command. See [dependency-automation.md](dependency-automation.md) for bot ownership and
activation evidence.

### Documentation

```bash
python scripts/check_versions.py
python scripts/check_docs_truth.py
python scripts/check_task_docs.py
cd fovux-mcp && uv run python scripts/check_tool_docs.py
uv run mkdocs build --strict
uv run python ../scripts/lint_docs_code.py ..
```

### Build

```bash
cd fovux-mcp && uv build
cd ../fovux-studio && corepack pnpm@10.34.1 --ignore-workspace run build
cd ../fovux-mcp-npm && npm pack --dry-run
```

## Before push

The pre-push hook runs `task pre-push` after `task hooks` is installed. Before a larger PR or release
change, run:

```bash
task ci
```

## Troubleshooting

- `task: command not found`: run `scripts/bootstrap-dev.sh` on Linux/macOS, or install
  `github.com/go-task/task/v3/cmd/task@v3.50.0` with Go on Windows.
- `pnpm: command not found`: run `corepack enable && corepack prepare pnpm@10.34.1 --activate`.
- `uv: command not found`: install `uv` from the official Astral documentation and rerun
  `task install`.
- `actionlint` or `gitleaks` missing: rerun the bootstrap script or install the pinned Go commands
  listed above.
- `task ci` fails but CI passes, or vice versa: compare local runtime versions with
  [runtime-compatibility.md](runtime-compatibility.md), then rerun `task install`.

## Optional local GitHub Actions simulation

```bash
# https://github.com/nektos/act
brew install act    # or download from releases
act --list          # see all jobs across all workflows
act -W .github/workflows/ci.yml
```
