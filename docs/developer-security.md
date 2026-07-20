# Developer Security Gates

Fovux Kit separates fast deterministic checks from credential-dependent cloud scanners. This keeps
normal commits reliable while preserving authoritative pull-request analysis.

## Semgrep

Repository-owned rules live under `.semgrep/rules/`. Each YAML rule file has a colocated positive
and negative fixture file. The current rules block high-confidence shell execution, dynamic code
execution, unsafe YAML loading, interpolated child-process execution, and credential logging.

Run locally:

```bash
task security:semgrep
```

The normal pre-commit stage runs Semgrep only for staged production Python, TypeScript, TSX, and
JavaScript files. CI scans the complete production source set and publishes SARIF to GitHub code
scanning. Local Semgrep runs use `--metrics=off`.

## Snyk

Install the Snyk CLI separately and export `SNYK_TOKEN` in the shell or an ignored `.env` file. The
token must never be committed.

```bash
SNYK_TOKEN=... task security:snyk
python scripts/run_snyk.py --required
```

The wrapper runs:

1. `snyk test --all-projects --severity-threshold=high`;
2. `snyk code test --severity-threshold=high`.

The pre-push hook invokes the same wrapper. When the executable or token is absent, the default local
command prints an explicit `SKIP` and exits successfully so unaffiliated contributors are not blocked.
`--required` changes missing configuration into exit code `2`. Once a scan starts, its non-zero exit
code is propagated unchanged. The hosted Snyk pull-request integration remains the authoritative
cloud check.

## SonarQube Cloud

Install SonarScanner separately and export `SONAR_TOKEN`. Sonar analysis is manual-only because it
uploads repository-wide state.

Branch analysis:

```bash
SONAR_TOKEN=... task security:sonar -- --branch feature/security
```

The current non-detached git branch is used when `--branch` is omitted:

```bash
SONAR_TOKEN=... task security:sonar
```

Pull-request analysis:

```bash
SONAR_TOKEN=... task security:sonar -- \
  --pull-request 138 \
  --branch feature/security \
  --base main
```

The wrapper never puts `SONAR_TOKEN` on the command line. Missing local setup is an explicit `SKIP`
unless `--required` is supplied. Scanner failures remain failures. The hosted SonarQube Cloud PR
integration remains authoritative.

## Pre-commit stages

Install all repository hook types with:

```bash
task hooks
```

The stages are:

- `pre-commit`: formatting, linting, secret checks, and staged-file Semgrep;
- `pre-push`: CI parity plus optional Snyk maintainer scan;
- `manual`: Snyk and Sonar maintainer commands.

Run manual hooks directly:

```bash
cd fovux-mcp
uv run pre-commit run snyk-maintainer --hook-stage manual --all-files
uv run pre-commit run sonar-maintainer --hook-stage manual --all-files
```

The Sonar manual hook uses the current branch. Use the Taskfile command when pull-request metadata or
an explicit branch is required.

## Secrets and outputs

`SNYK_TOKEN` and `SONAR_TOKEN` are read from environment variables only. Scanner wrappers use argument
arrays rather than shell interpolation and redact known token values in displayed commands. Local
caches, SARIF, JSON reports, and scanner logs are ignored through `.gitignore`.

Existing CodeQL, Trivy, OSV Scanner, pip-audit, npm/pnpm audits, Gitleaks, hosted Snyk, and hosted
Sonar controls remain enabled.
