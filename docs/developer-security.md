# Developer Security Gates

Fovux Kit separates deterministic repository-owned checks from the one credential-dependent quality
scanner. Normal commits and dependency scans do not require a third-party account.

## Canonical required local aggregate

Run every deterministic credential-free gate that has a meaningful single-machine equivalent with:

```bash
task verify:required
```

The aggregate runs the primary quality lane, including pinned Gitleaks `8.30.1`, plus
repository-specific Renovate validation, pinned Semgrep rules and fixtures, Trivy `0.70.0`
filesystem vulnerability scanning, and OSV-Scanner `2.3.8` scans for every committed lockfile. It
does not repeat the three-OS/Python or Node compatibility matrices.

`required-local-gates.json` maps each job feeding `ci-required` and `security-required` to either a
reachable Taskfile command or a documented hosted-only reason. `python scripts/check_required_local_gates.py`
fails when a required aggregate job is added, removed, or disconnected from `task verify:required`
without updating that contract.

The hosted-only boundaries are CodeQL, GitHub Dependency Review, OpenSSF Scorecard, strict GitHub
repository posture inspection, and the OS/runtime compatibility matrices. These require provider
metadata, privileged APIs, or distinct hosted runtimes and remain authoritative in GitHub Actions.

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

## OSV-Scanner

OSV-Scanner is the primary credential-free dependency vulnerability scanner. The bootstrap script
installs the pinned `v2.3.8` CLI through Go; no account or token is required.

```bash
task security:osv
python scripts/run_osv.py --required
```

The wrapper scans the Python, Studio, and npm-wrapper lockfiles. The pre-push hook invokes the same
command. Its default mode prints an explicit `SKIP` when the executable is absent or differs from the
repository pin so contributors who have not run the bootstrap are not blocked; `--required` converts
that condition into exit code `2`. Once scanning starts, the scanner exit code is propagated
unchanged.

GitHub Actions uses SHA-pinned OSV-Scanner v2 reusable workflows in two modes:

- pull requests and merge groups compare the base and head dependency sets and fail only when the
  change introduces a new known vulnerability;
- main pushes, schedules, and manual runs perform a full lockfile scan and publish SARIF to GitHub
  code scanning.

GitHub Dependency Review remains the PR dependency-policy gate, while Dependabot alerts and security
updates remain enabled. This avoids replacing Snyk with another overlapping commercial SAST suite.

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
SONAR_TOKEN=... task security:sonar --   --pull-request 138   --branch feature/security   --base main
```

The wrapper never puts `SONAR_TOKEN` on the command line. Missing local setup is an explicit `SKIP`
unless `--required` is supplied. Scanner failures remain failures. The hosted SonarQube Cloud PR
integration remains authoritative for maintainability and quality.

## Pre-commit stages

Install all repository hook types with:

```bash
task hooks
```

The stages are:

- `pre-commit`: formatting, linting, secret checks, and staged-file Semgrep;
- `pre-push`: fast type, test, workflow, and credential-free OSV checks;
- `manual`: OSV and Sonar maintainer commands.

Run manual hooks directly:

```bash
cd fovux-mcp
uv run pre-commit run osv-maintainer --hook-stage manual --all-files
uv run pre-commit run sonar-maintainer --hook-stage manual --all-files
```

The Sonar manual hook uses the current branch. Use the Taskfile command when pull-request metadata or
an explicit branch is required.

## Secrets and outputs

Only `SONAR_TOKEN` is read by the remaining credential-aware scanner wrapper. Scanner wrappers use
argument arrays rather than shell interpolation and redact known token values in displayed commands.
Local caches, SARIF, JSON reports, and scanner logs are ignored through `.gitignore`.

The active layered stack is CodeQL plus repository-owned Semgrep for SAST, OSV-Scanner plus GitHub
Dependency Review and Dependabot for dependency risk, Trivy for filesystem/container/IaC coverage,
pip/npm/pnpm audits for ecosystem-native checks, Gitleaks for secrets, and SonarQube Cloud for
maintainability. Snyk was retired on 21 July 2026 because its account limits no longer matched the
repository's open-source workflow.
