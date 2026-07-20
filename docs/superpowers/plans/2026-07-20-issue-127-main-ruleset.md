# Issue 127 Main Ruleset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the live solo-maintainer `main` ruleset and the tracked JSON policy identical, require the four stable aggregate quality/security checks, and fail CI when the live policy drifts.

**Architecture:** Treat `.github/rulesets/main.json` as the canonical policy. Normalize server-only GitHub API metadata and ordering before exact comparison, while preserving semantic fields such as rule parameters, strict status checks, branch conditions, and bypass actors. The security posture generator loads this file rather than hardcoding a second policy.

**Tech Stack:** Python 3.12+, pytest, GitHub REST API, GitHub rulesets, JSON, Markdown.

## Global Constraints

- Required checks: `ci-required`, `security-required`, `dependency-review`, `codeql-required`.
- Strict required-status-check policy remains enabled.
- No bypass actors.
- Pull requests and resolved review threads remain required with zero mandatory approvals for the solo-maintainer model.
- Do not require signed commits, Scorecard, or release-please until their coverage and contributor ergonomics are separately approved.
- Apply the live policy by ruleset ID; do not create a duplicate ruleset.

---

### Task 1: Define the canonical policy contract

**Files:**
- Modify: `.github/rulesets/main.json`
- Create: `fovux-mcp/tests/unit/test_security_posture_ruleset.py`

- [x] **Step 1: Write failing policy tests**

Add tests that require the canonical name/branch target, exactly four aggregate checks, strict status checking, zero bypass actors, no signature rule, and semantic equivalence despite API metadata/order differences.

- [x] **Step 2: Run the focused tests and confirm RED**

```bash
cd fovux-mcp
uv run pytest tests/unit/test_security_posture_ruleset.py -q --no-header
```

Expected: FAIL because the current tracked ruleset and posture script use the obsolete policy.

- [x] **Step 3: Update the canonical ruleset JSON**

Make `main.json` match the active solo-maintainer rule shape and the four required checks.

### Task 2: Replace hardcoded posture expectations with exact drift comparison

**Files:**
- Modify: `scripts/generate_security_posture.py`
- Modify: `fovux-mcp/tests/unit/test_security_posture_ruleset.py`

- [x] **Step 1: Add policy loading and normalization helpers**

Load the tracked JSON and normalize rule ordering, status-check ordering, and server-only API metadata.

- [x] **Step 2: Compare live and tracked policies**

Find the live ruleset by canonical name and report missing rulesets, bypass actors, or semantic mismatches as strict deviations.

- [x] **Step 3: Generate report labels from the canonical policy**

Remove obsolete `main-protection` and hardcoded check/signature assumptions from report output.

- [x] **Step 4: Run focused tests and confirm GREEN**

### Task 3: Update governance documentation and apply the live policy

**Files:**
- Modify: `.github/rulesets/README.md`
- Modify: `docs/branch-protection.md`
- Modify: `docs/security-posture.md` if regenerated evidence changes it

- [x] **Step 1: Document the exact solo-maintainer policy**

Explain the four checks, strict mode, no bypass actors, and why signatures/Scorecard/release-please are not required yet.

- [x] **Step 2: Validate the request payload**

Use JSON parsing, focused tests, and the posture script against a mocked/equivalent live policy.

- [x] **Step 3: Update ruleset ID 18689082 via PUT**

Apply `.github/rulesets/main.json` to the existing live ruleset and immediately read it back.

- [x] **Step 4: Run strict live drift validation**

```bash
python3 scripts/generate_security_posture.py --strict
```

Expected: no ruleset drift. The command currently exits 1 only for the open default-branch High Dependabot alert remediated by #135; the report contains no ruleset deviation.

### Task 4: Verify and publish the implementation

- [x] **Step 1: Run focused and repository checks**

Run pytest, Ruff/format/mypy for changed Python code, docs checks, actionlint where applicable, and `git diff --check`.

- [x] **Step 2: Attach API evidence to issue/PR**

Include live ruleset ID, required checks, strict mode, zero bypass actors, and tracked/live comparison result.

- [x] **Step 3: Commit, push, and open a PR**

Use conventional commits and `Closes #127` in the PR body.
