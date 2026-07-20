# Issue 138 Developer Security Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fast repository-owned Semgrep checks plus credential-aware Snyk and Sonar developer commands while preserving hosted CI authority.

**Architecture:** Semgrep is deterministic and runs at pre-commit plus full-repository CI with SARIF. Snyk and Sonar are wrapped by Python scripts that validate executables/tokens, use argument arrays, redact secrets, and distinguish local-not-configured from authenticated failure. Snyk is optional pre-push/manual; Sonar is manual only. Existing hosted Snyk/Sonar integrations remain authoritative.

**Tech Stack:** Semgrep 1.170.0, Python 3.12, pre-commit, pytest, GitHub Actions SARIF, Taskfile, Snyk CLI, SonarScanner CLI.

## Global Constraints

- Never store or print `SNYK_TOKEN` or `SONAR_TOKEN`.
- Semgrep local execution uses `--metrics=off` and repository-owned rules.
- Semgrep CI scans full relevant source, emits SARIF, and is included in `security-required`.
- Missing local Snyk/Sonar credentials are explicit skips; authenticated scanner failures remain failures.
- Snyk does not block contributors without credentials; hosted Snyk PR checks remain authoritative.
- Sonar is manual locally and existing SonarQube Cloud PR analysis remains authoritative.
- Existing CodeQL, Trivy, OSV, audit, Gitleaks, Snyk, and Sonar controls must remain operational.

---

### Task 1: Add high-confidence Semgrep rules and fixtures

**Files:**
- Create: `.semgrep.yml`
- Create: `.semgrep/rules/python-security.yml`
- Create: `.semgrep/rules/typescript-security.yml`
- Create: `.semgrep/rules/python-security.py`
- Create: `.semgrep/rules/typescript-security.ts`
- Create: `.semgrepignore`

**Interfaces:**
- Consumes: Python and TypeScript production source.
- Produces: blocking ERROR rules with rule IDs prefixed `fovux.python.` and `fovux.typescript.`.

- [ ] **Step 1: Create fixtures before rules**

Add `ruleid` and `ok` annotations for:

- Python subprocess `shell=True`;
- Python `eval` and `exec`;
- unsafe `yaml.load`/`yaml.unsafe_load`;
- TypeScript `child_process.exec` with template/concatenated input;
- TypeScript `eval`/`new Function`;
- logging variables named token/authorization/bearer.

- [ ] **Step 2: Preserve RED**

```bash
semgrep test .semgrep/rules
```

Expected: FAIL because rules do not exist.

- [ ] **Step 3: Implement minimal rules**

Each rule must set `severity: ERROR`, include a remediation message, and scope paths to production source where appropriate. Avoid heuristic path-boundary and CSP rules until a high-confidence pattern exists.

- [ ] **Step 4: Verify rule tests and repository baseline**

```bash
semgrep validate .semgrep/rules
semgrep test .semgrep/rules
semgrep scan --config .semgrep/rules --metrics=off --error \
  fovux-mcp/src fovux-studio/src fovux-mcp-npm/bin
```

Expected: fixtures pass and current production source has zero unexplained blocking findings. Add narrow `nosemgrep` suppressions only with a review explanation.

- [ ] **Step 5: Commit**

```bash
git add .semgrep.yml .semgrepignore .semgrep/rules .semgrep/tests
git commit -m "feat(security): add repository Semgrep rules"
```

### Task 2: Add Semgrep to pre-commit

**Files:**
- Modify: `.pre-commit-config.yaml`

**Interfaces:**
- Consumes: Semgrep rules from Task 1.
- Produces: pinned staged-file hook `semgrep-fovux`.

- [ ] **Step 1: Add pinned hook**

Use `https://github.com/semgrep/pre-commit`, revision `v1.170.0`, with:

```yaml
args:
  - --config=.semgrep/rules
  - --metrics=off
  - --error
files: ^(fovux-mcp/src/.*\.py|fovux-studio/src/.*\.(ts|tsx|js)|fovux-mcp-npm/bin/.*\.js)$
```

- [ ] **Step 2: Validate hook configuration**

```bash
cd fovux-mcp
uv run pre-commit validate-config ../.pre-commit-config.yaml
uv run pre-commit run semgrep-fovux --all-files
```

Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "feat(security): run Semgrep before commit"
```

### Task 3: Add credential-aware scanner wrappers with tests

**Files:**
- Create: `scripts/scanner_runner.py`
- Create: `scripts/run_snyk.py`
- Create: `scripts/run_sonar.py`
- Create: `fovux-mcp/tests/unit/test_scanner_wrappers.py`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `run_scanner(command: Sequence[str], token_names: Sequence[str], ...) -> int` and wrapper CLI exit codes.
- Exit 0 means passed or explicitly skipped because local credentials/executable are absent; output must state which case occurred.
- Authenticated scanner non-zero exits propagate unchanged.

- [ ] **Step 1: Write failing unit tests**

Test missing executable, missing token, successful subprocess, failed subprocess, token redaction, Snyk command construction, Sonar branch/PR command construction, and ignored output paths.

- [ ] **Step 2: Preserve RED**

```bash
cd fovux-mcp
uv run pytest tests/unit/test_scanner_wrappers.py -q --no-header
```

Expected: FAIL because wrappers do not exist.

- [ ] **Step 3: Implement shared runner**

Use `subprocess.run(list(command), check=False, env=redacted_env)` without shell interpolation. Never print complete environments or authenticated URLs. Print `SKIP: ... not configured locally` for absent executable/token.

- [ ] **Step 4: Implement Snyk wrapper**

Run, from repo root:

```text
snyk test --all-projects --severity-threshold=high
snyk code test --severity-threshold=high
```

Support `--required` to turn missing executable/token into failure for maintainer automation; default local behavior is explicit skip.

- [ ] **Step 5: Implement Sonar wrapper**

Require an explicit `--branch NAME` or `--pull-request NUMBER --base BASE --branch NAME`. Invoke `sonar-scanner` with `-Dsonar.token=...` supplied through environment or a masked mechanism that is not echoed. Default local behavior is explicit skip; `--required` fails when not configured.

- [ ] **Step 6: Ignore outputs**

Ignore `.scanner-cache/`, `.sonar/`, `.sonar-scanner/`, `.semgrep-cache/`, `semgrep-results.sarif`, `snyk-results.json`, and local scanner logs.

- [ ] **Step 7: Run quality checks and commit**

```bash
cd fovux-mcp
uv run ruff check ../scripts/scanner_runner.py ../scripts/run_snyk.py ../scripts/run_sonar.py tests/unit/test_scanner_wrappers.py
uv run ruff format --check ../scripts/scanner_runner.py ../scripts/run_snyk.py ../scripts/run_sonar.py tests/unit/test_scanner_wrappers.py
uv run mypy --strict ../scripts/scanner_runner.py ../scripts/run_snyk.py ../scripts/run_sonar.py
uv run pytest tests/unit/test_scanner_wrappers.py -q --no-header
cd ..
git add scripts/scanner_runner.py scripts/run_snyk.py scripts/run_sonar.py \
  fovux-mcp/tests/unit/test_scanner_wrappers.py .gitignore
git commit -m "feat(security): add Snyk and Sonar developer wrappers"
```

### Task 4: Wire Taskfile and pre-commit stages

**Files:**
- Modify: `Taskfile.yml`
- Modify: `.pre-commit-config.yaml`
- Modify: `docs/development.md`
- Modify: `docs/security.md` or create `docs/developer-security.md`.

**Interfaces:**
- Produces: `security:semgrep`, `security:snyk`, `security:sonar`, and manual/pre-push hooks.

- [ ] **Step 0: Keep Semgrep out of the compatibility matrix**

The broad `security` task is executed in every compatibility-matrix cell and must not invoke
`security:semgrep`. Semgrep remains available through `security:semgrep`, `security:developer`,
pre-commit, and the independent required SARIF job. This avoids eighteen duplicate Semgrep runs.

- [ ] **Step 1: Add Taskfile tasks**

```yaml
  security:semgrep:
    cmds:
      - semgrep test .semgrep/rules
      - semgrep scan --config .semgrep/rules --metrics=off --error fovux-mcp/src fovux-studio/src fovux-mcp-npm/bin
  security:snyk:
    cmds:
      - python scripts/run_snyk.py
  security:sonar:
    cmds:
      - python scripts/run_sonar.py {{.CLI_ARGS}}
```

- [ ] **Step 2: Add Snyk and Sonar hooks**

Add local hooks:

- `snyk-maintainer` at `pre-push`, `pass_filenames: false`, wrapper default skip semantics;
- `sonar-maintainer` at `manual`, `pass_filenames: false`, requiring CLI arguments through direct Taskfile/manual execution when branch/PR metadata is needed.

- [ ] **Step 3: Document installation and authority**

Explain tokens, CLI installation, explicit skip semantics, `--required`, hosted-check authority, and manual Sonar examples without embedding credentials.

- [ ] **Step 4: Validate and commit**

```bash
cd fovux-mcp
uv run pre-commit validate-config ../.pre-commit-config.yaml
cd ..
python3 scripts/check_task_docs.py
python3 scripts/lint_docs_code.py .
git add Taskfile.yml .pre-commit-config.yaml docs
git commit -m "docs(security): add developer scanner commands"
```

### Task 5: Add authoritative Semgrep CI and SARIF

**Files:**
- Modify: `.github/workflows/security.yml`

**Interfaces:**
- Produces: `Semgrep SAST` job and `SEMGREP_RESULT` dependency in `security-required`.

- [ ] **Step 1: Add pinned Semgrep job**

Use Python 3.12 plus a pinned `semgrep==1.170.0` installation or a digest-pinned official image. Run rule validation/tests first, then full scan with:

```bash
semgrep scan --config .semgrep/rules --metrics=off --error \
  --sarif-output semgrep-results.sarif \
  fovux-mcp/src fovux-studio/src fovux-mcp-npm/bin
```

- [ ] **Step 2: Upload SARIF**

Use the repository-pinned CodeQL upload action with `if: always() && hashFiles(semgrep-results.sarif) != ` and category `semgrep-fovux`.

- [ ] **Step 3: Add to aggregate**

Add `semgrep` to `security-required.needs`, expose `SEMGREP_RESULT`, and fail unless it equals `success`.

- [ ] **Step 4: Validate workflow**

```bash
actionlint
python3 - <<"PY"
from pathlib import Path
text = Path(".github/workflows/security.yml").read_text()
assert "Semgrep SAST" in text
assert "semgrep-results.sarif" in text
assert "SEMGREP_RESULT" in text
PY
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/security.yml
git commit -m "feat(security): require Semgrep SAST"
```

### Task 6: Add Sonar project configuration

**Files:**
- Create: `sonar-project.properties`

**Interfaces:**
- Consumes: repository source and existing coverage report locations.
- Produces: stable local scanner scope matching hosted project `oaslananka_fovux-kit`.

- [ ] **Step 1: Add project settings**

Set project key, source/test roots, Python coverage report, JS/TS coverage report, test inclusions, and exclusions for lockfiles, generated output, virtualenvs, fixtures, reports, docs, and vendored files.

- [ ] **Step 2: Validate wrapper command construction**

Run unit tests and a no-token local invocation:

```bash
python3 scripts/run_sonar.py --branch local-validation
```

Expected: exit 0 with explicit `SKIP: SONAR_TOKEN not configured locally`; no false success message.

- [ ] **Step 3: Commit**

```bash
git add sonar-project.properties
git commit -m "chore(security): configure local Sonar analysis"
```

### Task 7: Final verification

**Files:** all changed files.

- [ ] **Step 1: Run focused gates**

```bash
semgrep validate .semgrep/rules
semgrep test .semgrep/rules
semgrep scan --config .semgrep/rules --metrics=off --error fovux-mcp/src fovux-studio/src fovux-mcp-npm/bin
cd fovux-mcp
uv run pytest tests/unit/test_scanner_wrappers.py -q --no-header
uv run pre-commit validate-config ../.pre-commit-config.yaml
cd ..
actionlint
python3 scripts/check_task_docs.py
python3 scripts/check_docs_truth.py
```

- [ ] **Step 2: Run regression suites**

```bash
cd fovux-mcp
uv run pytest -q --no-header --basetemp=/tmp/fovux-kit-138-pytest
cd ../fovux-studio
corepack pnpm@10.34.1 --ignore-workspace test --run
```

- [ ] **Step 3: Review diff**

```bash
git diff --check
git status --short
git log --oneline --decorate -12
```

Expected: clean worktree and all checks pass.
