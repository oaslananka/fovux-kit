# Elevated Pull Request Review Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Require explicit, machine-checkable, SHA-bound review evidence for high-risk and `size/XL` pull requests while preserving a transparent solo-maintainer path and leaving routine low-risk changes unblocked.

**Architecture:** Store the elevated-review classification and evidence contract in a repository-owned JSON policy. A pure-Python checker provides testable classification/evidence functions and a read-only GitHub metadata client. A base-branch `pull_request_target` workflow checks out only the trusted base SHA and publishes the `elevated-review-required` commit status on the pull-request head; a second activation pull request adds that status to the tracked/live `main` ruleset after the workflow exists on `main`.

**Tech Stack:** Python 3.12+ standard library, GitHub REST/GraphQL APIs, GitHub Actions, JSON policy, pytest, Ruff, mypy, actionlint.

## Global Constraints

- Preserve the current solo-maintainer ruleset approval count of `0`; elevated review is enforced through an additional required job check, not a blanket approval rule.
- Use a base-only `pull_request_target` metadata gate, checkout the trusted `github.event.pull_request.base.sha`, and never fetch or execute pull-request head code.
- Classify elevated changes from immutable changed-file paths as well as labels; labels alone must never be the only sensitive-change signal.
- Bind every accepted body evidence and external approval to the current 40-character pull-request head SHA so any push invalidates stale evidence.
- Keep `ci-required`, `security-required`, `dependency-review`, and `codeql-required` mandatory.
- Treat unresolved review threads and failed/pending required checks as blocking states.
- Require a public structured pull-request body evidence for every elevated pull request; external-contributor pull requests additionally require a current-head approval from an authorized non-author reviewer.
- Keep all workflow actions SHA-pinned and permissions least-privileged.

---

### Task 1: Define the elevated-review policy and classification contract

**Files:**

- Create: `.github/review-evidence-policy.json`
- Create: `scripts/check_review_evidence.py`
- Create: `fovux-mcp/tests/unit/test_review_evidence.py`

**Interfaces:**

- Produces: `load_policy(path: Path) -> dict[str, object]`
- Produces: `classify_elevated(labels: Collection[str], files: Collection[str], policy: Mapping[str, object]) -> Classification`
- Produces: `Classification(elevated: bool, label_reasons: tuple[str, ...], path_reasons: tuple[str, ...])`

- [ ] **Step 1: Write failing policy and classification tests**

Add tests proving that `risk:high`, `size/XL`, and `requires-review` elevate a pull request; authentication, authorization, subprocess, workflow-permission, publishing, registry, schema, and migration paths elevate without labels; ordinary docs-only paths remain routine; and malformed policy documents fail closed.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
/tmp/fovux91-venv/bin/python -m pytest -q fovux-mcp/tests/unit/test_review_evidence.py
```

Expected: FAIL because the policy and checker do not exist.

- [ ] **Step 3: Implement the minimal policy loader and classifier**

The JSON policy must define:

```json
{
    "status_context": "elevated-review-required",
    "elevated_labels": ["risk:high", "size/XL", "requires-review"],
    "sensitive_paths": [
        {
            "category": "authentication-authorization",
            "patterns": ["fovux-mcp/src/fovux/core/auth.py"]
        },
        {
            "category": "subprocess-execution",
            "patterns": ["fovux-mcp/src/fovux/core/processes.py"]
        },
        {
            "category": "workflow-permissions",
            "patterns": [".github/workflows/**", ".github/rulesets/**"]
        },
        {
            "category": "release-publishing",
            "patterns": [
                "scripts/publish*",
                "scripts/*release*",
                ".github/workflows/publish-production.yml",
                ".github/workflows/release-please.yml"
            ]
        },
        {
            "category": "registry-schema-migration",
            "patterns": [
                "fovux-mcp/src/fovux/core/tool_registry.py",
                "fovux-mcp/src/fovux/core/runs.py",
                "fovux-mcp/src/fovux/schemas/**",
                "**/migrations/**",
                "**/alembic/**"
            ]
        }
    ]
}
```

Use `fnmatch.fnmatchcase` for repository-relative POSIX paths and return stable, sorted reason tuples.

- [ ] **Step 4: Run tests and verify GREEN**

Run the focused test file and Ruff check/format on the new Python files.

- [ ] **Step 5: Commit the policy foundation**

```bash
git add .github/review-evidence-policy.json scripts/check_review_evidence.py fovux-mcp/tests/unit/test_review_evidence.py
git commit -m "governance: define elevated review policy"
```

### Task 2: Implement SHA-bound evidence and external-review evaluation

**Files:**

- Modify: `scripts/check_review_evidence.py`
- Modify: `fovux-mcp/tests/unit/test_review_evidence.py`

**Interfaces:**

- Produces: `parse_evidence_body(body: str, *, head_sha: str, policy: Mapping[str, object]) -> Evidence | None`
- Produces: `evaluate_review_evidence(pr: PullRequestSnapshot, policy: Mapping[str, object]) -> Decision`
- Produces: `Decision(state: Literal["success", "pending", "failure"], description: str, reasons: tuple[str, ...])`

- [ ] **Step 1: Write failing evidence tests**

Cover these behaviors independently:

1. routine PR succeeds without evidence;
2. maintainer-authored elevated PR requires public `<!-- elevated-review-evidence -->` data in the pull request body;
3. evidence must include exact `Head SHA`, matching `Reviewer`, non-placeholder `Risk assessment`, `Validation evidence`, `Bot/agent findings`, and `Residual risk` fields;
4. stale-SHA evidence is rejected after a push;
5. required checks must all be successful and unresolved review threads must be zero;
6. a failed required check produces `failure`, while missing/pending checks produce `pending`;
7. external-contributor PRs require a current-head approval by an authorized non-author reviewer in addition to the body evidence;
8. dismissed, stale-commit, author-self, or unauthorized approvals do not count;
9. evidence must explicitly mention every required check context and summarize bot/agent findings rather than using an empty placeholder.

- [ ] **Step 2: Run tests and verify RED**

Expected: failures for missing evidence parsing/evaluation functions.

- [ ] **Step 3: Implement minimal immutable snapshots and decisions**

Use immutable pull-request snapshots, reviews, check contexts, evidence, and decisions. Authorized associations are `OWNER`, `MEMBER`, and `COLLABORATOR`. For maintainer-authored pull requests, `Reviewer: @login` must match the pull-request author. External pull requests must name an authorized reviewer whose current-head approval independently proves review. All structured fields are bound to the current head SHA.

- [ ] **Step 4: Run tests and verify GREEN**

Run the focused test file, Ruff, and strict mypy for the checker.

- [ ] **Step 5: Commit evidence evaluation**

```bash
git add scripts/check_review_evidence.py fovux-mcp/tests/unit/test_review_evidence.py
git commit -m "governance: evaluate SHA-bound review evidence"
```

### Task 3: Add the base-only metadata gate

**Files:**

- Create: `.github/workflows/review-evidence-gate.yml`
- Modify: `scripts/check_review_evidence.py`
- Modify: `fovux-mcp/tests/unit/test_review_evidence.py`

**Interfaces:**

- Produces CLI: `python scripts/check_review_evidence.py --event-path PATH --repository OWNER/REPO --token-env GITHUB_TOKEN`
- Writes commit status context: `elevated-review-required`
- Static mode: `python scripts/check_review_evidence.py --validate-repository`

- [ ] **Step 1: Write failing workflow/runtime tests**

Tests must prove that the workflow:

- uses only `pull_request_target` metadata events, including `edited` for final body evidence;
- has only `contents: read`, `pull-requests: read`, `checks: read`, and `statuses: write` permissions;
- explicitly checks out `github.event.pull_request.base.sha` with `persist-credentials: false`;
- never references `pull_request.head`, `github.head_ref`, `refs/pull`, `gh pr checkout`, or fetches PR code;
- invokes only the base-branch checker;
- publishes the `elevated-review-required` head commit status while preserving all existing required contexts for the later activation PR.

- [ ] **Step 2: Run tests and verify RED**

Expected: missing workflow/runtime/ruleset failures.

- [ ] **Step 3: Implement GitHub API runtime**

Resolve the pull-request number from the standard event. Query pull-request details and body, paginated files, labels, reviews, review threads, combined status contexts, and check runs. Evaluate the immutable snapshot and publish `success`, `pending`, or `failure` to the configured head commit status. Exit nonzero only when the metadata/API operation itself fails.

- [ ] **Step 4: Implement safe workflow and ruleset update**

The workflow must run only base-branch policy code and set a 5-minute timeout. Do not modify `.github/rulesets/main.json` in the bootstrap PR. The strict live-ruleset drift check must remain green until the workflow is available on `main`.

- [ ] **Step 5: Run tests and verify GREEN**

Run focused tests, actionlint, YAML lint, JSON validation, Ruff, and strict mypy.

- [ ] **Step 6: Commit the hosted gate**

```bash
git add .github/workflows/review-evidence-gate.yml scripts/check_review_evidence.py fovux-mcp/tests/unit/test_review_evidence.py
git commit -m "ci: require elevated review evidence"
```

### Task 4: Synchronize template, policy docs, local drift checks, and governance docs

**Files:**

- Create: `docs/elevated-review-policy.md`
- Modify: `.github/PULL_REQUEST_TEMPLATE.md`
- Modify: `docs/branch-protection.md`
- Modify: `scripts/check_governance_lifecycle.py`
- Modify: `Taskfile.yml`
- Modify: `fovux-mcp/tests/unit/test_review_evidence.py`

**Interfaces:**

- Repository validation guarantees that policy JSON, workflow context, ruleset context, PR template, and documentation use the same marker/context/required-check set.

- [ ] **Step 1: Write failing repository-drift tests**

Tests must fail when the PR template lacks the structured evidence section, when docs omit a sensitive category or solo/external path, when the ruleset/context diverges, when required checks are removed, or when the workflow loses safe event/permission constraints.

- [ ] **Step 2: Run tests and verify RED**

Expected: documentation/template/Taskfile failures.

- [ ] **Step 3: Add the public policy and template**

Document classification, exact body evidence format, current-head approval rules, bot/agent finding acknowledgement, re-review after push, solo-maintainer and external-contributor paths, and the fact that routine low-risk changes pass the job check automatically.

Add this template section:

```markdown
## Elevated Review Evidence

Complete this after required checks finish when `risk:high`, `size/XL`, `requires-review`, or a sensitive path applies.

<!-- elevated-review-evidence -->

Head SHA:
Reviewer:
Risk assessment:
Validation evidence: ci-required, security-required, dependency-review, codeql-required, Review Threads
Bot/agent findings:
Residual risk:
```

- [ ] **Step 4: Wire static validation into local docs/CI checks**

Add `python scripts/check_review_evidence.py --validate-repository` to `task docs`, and make `check_governance_lifecycle.py` require the policy, workflow, template, and public policy document.

- [ ] **Step 5: Run tests and verify GREEN**

Run focused tests, docs truth, Taskfile reference checks, governance checker, Prettier, Ruff, actionlint, and strict mypy.

- [ ] **Step 6: Commit documentation and drift enforcement**

```bash
git add docs/elevated-review-policy.md .github/PULL_REQUEST_TEMPLATE.md docs/branch-protection.md scripts/check_governance_lifecycle.py Taskfile.yml fovux-mcp/tests/unit/test_review_evidence.py
git commit -m "docs: define elevated review evidence"
```

### Task 5: Bootstrap workflow verification, PR review, and merge

**Files:**

- Verify all files changed in Tasks 1-4.

- [ ] **Step 1: Run the full deterministic local gate**

```bash
task verify:required
```

Expected: exit `0`, no generated diff, all scanner and coverage gates pass.

- [ ] **Step 2: Run focused governance verification**

```bash
python scripts/check_review_evidence.py --validate-repository
python scripts/generate_security_posture.py --strict
/tmp/fovux91-venv/bin/python -m pytest -q \
  fovux-mcp/tests/unit/test_review_evidence.py \
  fovux-mcp/tests/unit/test_security_posture_ruleset.py
```

Expected: all pass; tracked and live rulesets remain unchanged during the workflow bootstrap PR.

- [ ] **Step 3: Push and open the pull request**

Open a public bootstrap PR that links #174 without closing it. Explain that ruleset activation follows in a second PR after the workflow exists on `main`.

- [ ] **Step 4: Inspect every bot and agent signal**

Review SonarQube, Codecov, CodeQL, Semgrep, Trivy, OSV, Dependency Review, Socket, DeepScan, Scorecard, review comments, inline comments, and unresolved threads. Fix or explicitly justify every finding.

- [ ] **Step 5: Merge only after all existing required checks pass**

The new commit status is not yet a live branch requirement for its own bootstrap PR. Add explicit maintainer review evidence to the PR body and merge only when the tracked policy and all existing gates are green.

### Task 6: Activate the required context in a second pull request

**Files:**

- Modify: `.github/rulesets/main.json`
- Modify: `fovux-mcp/tests/unit/test_security_posture_ruleset.py`
- Modify: `fovux-mcp/tests/unit/test_review_evidence.py`

- [ ] **Step 1: Create a fresh activation branch from the bootstrap merge**

Open a second pull request that adds `elevated-review-required` to the tracked ruleset, switches the policy phase to `active`, and updates the ruleset contract tests. The base branch now contains the base-only metadata workflow, so the activation PR receives the new commit status.

- [ ] **Step 2: Apply the tracked ruleset live while the activation PR is open**

```bash
gh api --method PUT repos/oaslananka/fovux-kit/rulesets/18689082 \
  --input .github/rulesets/main.json
```

Immediately rerun/observe Security Scanning so the strict posture check compares identical tracked/live policy.

- [ ] **Step 3: Verify and merge the activation PR**

Require the new `elevated-review-required` job check, all existing checks, explicit SHA-bound maintainer body evidence, and zero unresolved bot/agent findings. Merge only after the ruleset and workflow are both active.

- [ ] **Step 4: Verify post-merge policy**

```bash
python scripts/generate_security_posture.py --strict
```

Confirm main CI/security/CodeQL/Scorecard remain green, the issue closes, and no unexpected release PR is created.
