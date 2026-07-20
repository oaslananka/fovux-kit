# Issue 137 Renovate Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the inheritance-only Renovate file with a validated Fovux-specific monorepo policy and produce activation evidence without enabling unsafe scheduled mutation.

**Architecture:** Keep `oaslananka/.github:renovate-config` as the shared baseline, then add repository-local manager selection, package grouping, protected dependency rules, labels, schedules, and validation. A Python validator provides deterministic CI checks; Renovate CLI validation and lookup dry-runs provide tool-level evidence. GitHub-native Dependabot security updates remain enabled until a dedicated Renovate credential and successful real cycle are proven.

**Tech Stack:** Renovate 43.x, JSON, Python 3.12, pytest, GitHub Actions, Taskfile.

## Global Constraints

- Use the explicit preset `github>oaslananka/.github:renovate-config`.
- Enable only `pep621`, `npm`, `github-actions`, `dockerfile`, `nvm`, and `pre-commit` managers; `pep621` owns `uv.lock` maintenance.
- Use only labels already declared in `.github/labels.yml`.
- Never automerge MCP/FastMCP, Torch/YOLO/CUDA, computer-vision runtime, runtime-policy, or security/release tooling groups.
- Keep normal updates in a weekly Europe/Istanbul maintenance window; security remediation remains immediate.
- Do not add `.github/dependabot.yml` or disable GitHub security alerts in this change.
- Do not enable a scheduled central Renovate workflow until a dedicated `RENOVATE_TOKEN` has been proven.

---

### Task 1: Add deterministic Renovate policy validation

**Files:**
- Create: `scripts/validate_renovate_config.py`
- Create: `fovux-mcp/tests/unit/test_renovate_config.py`

**Interfaces:**
- Consumes: `renovate.json`, `.github/labels.yml`, known Fovux manifest paths.
- Produces: `validate_config(repo_root: Path) -> list[str]` and CLI exit 0/1.

- [ ] **Step 1: Write failing tests**

Create tests that assert:

```python
EXPECTED_MANAGERS = {
    "pep621", "npm", "github-actions", "dockerfile", "nvm", "pre-commit"
}
PROTECTED_PACKAGES = {"mcp", "fastmcp", "torch", "pillow", "onnxruntime"}
```

The tests must verify the explicit preset, enabled managers, all labels existing, protected rules having `automerge is False`, and the validator rejecting a missing manager or unknown label.

- [ ] **Step 2: Run tests and preserve RED**

Run:

```bash
cd fovux-mcp
uv run pytest tests/unit/test_renovate_config.py -q --no-header
```

Expected: FAIL because `scripts/validate_renovate_config.py` does not exist.

- [ ] **Step 3: Implement the validator**

Implement JSON loading, YAML label-name extraction without external dependencies, manager checks, manifest-path checks, protected-package checks, and a CLI:

```python
if __name__ == "__main__":
    errors = validate_config(REPO_ROOT)
    for error in errors:
        print(f"ERROR: {error}")
    raise SystemExit(1 if errors else 0)
```

- [ ] **Step 4: Run focused quality checks**

```bash
cd fovux-mcp
uv run ruff check ../scripts/validate_renovate_config.py tests/unit/test_renovate_config.py
uv run ruff format --check ../scripts/validate_renovate_config.py tests/unit/test_renovate_config.py
uv run mypy --strict ../scripts/validate_renovate_config.py
uv run pytest tests/unit/test_renovate_config.py -q --no-header
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/validate_renovate_config.py fovux-mcp/tests/unit/test_renovate_config.py
git commit -m "test(deps): add Renovate policy validation"
```

### Task 2: Implement the Fovux-specific Renovate policy

**Files:**
- Modify: `renovate.json`

**Interfaces:**
- Consumes: shared preset and validator from Task 1.
- Produces: schema-valid Renovate configuration with explicit manager and package policies.

- [ ] **Step 1: Expand `renovate.json`**

Set:

```json
{
  "$schema": "https://docs.renovatebot.com/renovate-schema.json",
  "extends": ["github>oaslananka/.github:renovate-config"],
  "enabledManagers": ["pep621", "uv", "npm", "github-actions", "dockerfile", "nvm", "pre-commit"],
  "timezone": "Europe/Istanbul",
  "schedule": ["after 02:00 and before 06:00 on monday"],
  "prHourlyLimit": 2,
  "prConcurrentLimit": 6,
  "labels": ["dependencies", "goal:supply-chain"],
  "dependencyDashboard": true,
  "dependencyDashboardTitle": "Dependency Dashboard"
}
```

Add package rules for the protected groups, component labels, lockfiles, security fixes, GitHub Actions, and pre-commit hooks. Every protected group must set `automerge: false` and `dependencyDashboardApproval: true` for major updates.

- [ ] **Step 2: Run the deterministic validator**

```bash
python3 scripts/validate_renovate_config.py
```

Expected: exit 0 and print a success summary with six managers and three component manifests.

- [ ] **Step 3: Run Renovate schema validation**

```bash
npx --yes renovate@43.272.4 renovate-config-validator renovate.json
```

Expected: configuration is valid.

- [ ] **Step 4: Commit**

```bash
git add renovate.json
git commit -m "feat(deps): add Fovux Renovate policy"
```

### Task 3: Add developer and CI entry points

**Files:**
- Modify: `Taskfile.yml`
- Modify: `.github/workflows/ci.yml`
- Modify: `docs/development.md`
- Create: `docs/dependency-automation.md`

**Interfaces:**
- Consumes: validator and Renovate config.
- Produces: `task deps:renovate:validate` and a CI validation step.

- [ ] **Step 1: Add Taskfile command**

Add:

```yaml
  deps:renovate:validate:
    desc: Validate Fovux-specific Renovate policy
    cmds:
      - python scripts/validate_renovate_config.py
      - npx --yes renovate@43.272.4 renovate-config-validator renovate.json
```

- [ ] **Step 2: Add CI validation**

Add a lightweight Ubuntu job or existing quality-lane step that runs the deterministic validator and pinned Renovate config validator. Do not add a token-backed mutation job to this repository.

- [ ] **Step 3: Document ownership and activation**

Document manager ownership, protected groups, Dependabot coexistence, required dedicated token, lookup dry-run, Dependency Dashboard proof, real PR proof, and rollback.

- [ ] **Step 4: Validate docs and workflow syntax**

```bash
actionlint
python3 scripts/check_task_docs.py
python3 scripts/lint_docs_code.py .
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add Taskfile.yml .github/workflows/ci.yml docs/development.md docs/dependency-automation.md
git commit -m "docs(deps): document Renovate activation"
```

### Task 4: Produce activation evidence without unsafe scheduling

**Files:**
- Create: `reports/renovate/.gitkeep` only if an ignored report directory is needed; prefer issue comments over committed logs.
- Update: issue #137 with evidence.

**Interfaces:**
- Consumes: central `oaslananka/.github` manual Renovate workflow and repository config.
- Produces: lookup evidence or an explicit external-token blocker.

- [ ] **Step 1: Run local lookup**

```bash
npx --yes renovate@43.272.4 \
  --platform=local \
  --dry-run=lookup \
  --require-config=required \
  .
```

Expected: Renovate discovers PEP 621/uv, npm/pnpm, Actions, Dockerfile, NVM, and pre-commit files. If local platform behavior differs, capture config extraction output with `LOG_LEVEL=debug` and do not claim full GitHub activation.

- [ ] **Step 2: Dispatch the central manual dry-run**

Trigger `.github/.github/workflows/renovate-manual.yml` with `dryRun=true`, then inspect logs. If `RENOVATE_TOKEN` is absent, record the missing external credential as the sole activation blocker and leave scheduling disabled.

- [ ] **Step 3: Record evidence on #137**

Include validator results, discovered managers, central run URL/conclusion, and whether the token prerequisite is satisfied. Do not close #137 unless a real Renovate dashboard and PR have been produced.

### Task 5: Final verification

**Files:** all changed files.

- [ ] **Step 1: Run repository checks**

```bash
python3 scripts/validate_renovate_config.py
cd fovux-mcp
uv run pytest tests/unit/test_renovate_config.py -q --no-header
uv run ruff check ../scripts/validate_renovate_config.py tests/unit/test_renovate_config.py
cd ..
actionlint
python3 scripts/check_task_docs.py
python3 scripts/check_docs_truth.py
```

- [ ] **Step 2: Review diff and commit any verification-only corrections**

```bash
git diff --check
git status --short
git log --oneline --decorate -8
```

Expected: clean worktree after focused commits.
