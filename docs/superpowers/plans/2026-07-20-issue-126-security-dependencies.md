# Issue 126 Security Dependencies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the known MCP and Pillow vulnerabilities from the locked `fovux-mcp` runtime dependency set without including the unrelated Torch 2.13 upgrade.

**Architecture:** Keep FastMCP as the high-level MCP integration while declaring an explicit MCP v1 security floor because MCP is a security-sensitive transitive runtime dependency. Raise the direct Pillow floor, refresh only the affected lockfile packages, and document the planned patch in release notes without claiming publication.

**Tech Stack:** Python 3.12+, uv, pip-audit, pytest, Ruff, mypy, Markdown.

## Global Constraints

- MCP must resolve to `>=1.28.1,<2`.
- Pillow must resolve to `>=12.3.0`.
- Torch 2.13 is out of scope and tracked separately in issue #134.
- The Setuptools advisory exception must be time-bounded and limited to the optional Torch/YOLO lock path.
- The remediation must preserve the current `fovux-mcp` public version until release automation cuts v1.4.1.
- Generated `requirements-audit.txt` must remain untracked.

---

### Task 1: Declare security floors and refresh the lockfile

**Files:**
- Modify: `fovux-mcp/pyproject.toml`
- Modify: `fovux-mcp/uv.lock`
- Modify: `fovux-mcp/osv-scanner.toml`
- Modify: `fovux-mcp/tests/contract/test_mcp_protocol.py`

**Interfaces:**
- Consumes: FastMCP 3.x runtime dependency graph.
- Produces: a deterministic lock with MCP v1 and Pillow versions above their fixed security floors.

- [x] **Step 1: Preserve the failing security reproduction**

Run:
```bash
cd fovux-mcp
uv sync --frozen --extra dev
uv export --no-dev --no-editable --no-emit-project --no-hashes --output-file requirements-audit.txt
uv run pip-audit --requirement requirements-audit.txt --strict
```
Expected: FAIL and report `mcp==1.28.0` plus `pillow==12.2.0`.

- [x] **Step 2: Add the minimum safe constraints**

Change the runtime dependency list to include:
```toml
"mcp>=1.28.1,<2",
"pillow>=12.3.0",
```
Keep `fastmcp>=3.3.1,<4` and all unrelated dependency constraints unchanged.

- [x] **Step 3: Refresh only the affected lock packages**

Run:
```bash
cd fovux-mcp
uv lock --upgrade-package mcp --upgrade-package pillow
```
Expected: `uv.lock` resolves MCP `1.28.1` or newer within v1 and Pillow `12.3.0` or newer, without changing Torch.

- [x] **Step 4: Verify lock constraints**

Run:
```bash
cd fovux-mcp
uv lock --check
python - <<'PY'
from pathlib import Path
import re
text = Path('uv.lock').read_text()
for name, minimum, major_limit in [('mcp', (1, 28, 1), 2), ('pillow', (12, 3, 0), None)]:
    match = re.search(rf'name = "{name}"\nversion = "([^"]+)"', text)
    assert match, name
    version = tuple(int(part) for part in match.group(1).split('.')[:3])
    assert version >= minimum, (name, version)
    if major_limit is not None:
        assert version[0] < major_limit, (name, version)
print('dependency floors verified')
PY
```
Expected: PASS and print `dependency floors verified`.

- [x] **Step 5: Verify the security scan turns green**

Run:
```bash
cd fovux-mcp
uv sync --frozen --extra dev
uv export --no-dev --no-editable --no-emit-project --no-hashes --output-file requirements-audit.txt
uv run pip-audit --requirement requirements-audit.txt --strict
uv run pip-audit --strict
```
Expected: both runtime audits exit 0 with no known vulnerabilities. Run the repository OSV scan and verify that only the documented, time-bounded optional Torch/Setuptools exception is filtered.

### Task 2: Make the raw stdio contract timeout cold-start tolerant

**Files:**
- Modify: `fovux-mcp/tests/contract/test_mcp_protocol.py`

**Interfaces:**
- Consumes: the existing raw JSON-RPC subprocess contract test.
- Produces: the same protocol assertions with a 30-second read deadline that accommodates measured cold-start registration time while still failing a hung server.

- [x] **Step 1: Reproduce the timeout**

Run the raw stdio contract with the original 10-second deadline. Expected: FAIL on VPS-2 while a manual probe returns a valid initialize response after approximately 15 seconds.

- [x] **Step 2: Compare the old MCP SDK**

Temporarily run the same test with MCP 1.28.0. Expected: the same timeout, proving the behavior is not introduced by MCP 1.28.1. Restore the frozen environment afterward.

- [x] **Step 3: Raise only the subprocess read deadline**

Set `_READ_TIMEOUT_SECONDS = 30` and retain all protocol assertions unchanged.

- [x] **Step 4: Verify the contract and full suite**

Run:
```bash
cd fovux-mcp
uv run pytest tests/contract/test_mcp_protocol.py::test_raw_stdio_jsonrpc_initialize_list_call_error_and_cancel -q --no-header
uv run pytest -x --no-header -q --basetemp=/tmp/fovux-kit-126-pytest-final
```
Expected: both commands exit 0.

### Task 3: Enforce Trivy severity filtering in SARIF mode

**Files:**
- Modify: `.github/workflows/security.yml`

**Interfaces:**
- Consumes: `aquasecurity/trivy-action` SARIF output with a configured `CRITICAL,HIGH` threshold.
- Produces: a security gate whose exit code is limited to the configured severities while SARIF remains uploaded.

- [x] **Step 1: Reproduce the workflow-only failure**

Observe PR #135 security run `29757924264`: direct pip-audit and OSV jobs pass, but Trivy 0.70.0 fails in SARIF mode on the tracked LOW optional-Torch advisory.

- [x] **Step 2: Verify upstream action behavior**

Inspect the pinned Trivy action entrypoint and confirm that SARIF mode unsets `TRIVY_SEVERITY` unless `limit-severities-for-sarif` is true.

- [x] **Step 3: Preserve the configured threshold**

Add:
```yaml
limit-severities-for-sarif: true
```
next to `severity: CRITICAL,HIGH` in the Trivy workflow step.

- [x] **Step 4: Validate workflow syntax and prepare the GitHub security rerun**

Run actionlint locally and verify Trivy 0.70.0 produces zero HIGH/CRITICAL SARIF results with the configured threshold. The replacement `security-required` result is recorded on PR #135.

### Task 4: Document and validate the patch

**Files:**
- Create: `docs/release-notes/1.4.1.md`

**Interfaces:**
- Consumes: the verified dependency lock from Task 1.
- Produces: release-facing evidence for the planned v1.4.1 security patch without modifying changelogs that are reserved for published releases.

- [x] **Step 1: Add planned security release notes**

Create `docs/release-notes/1.4.1.md` with an explicit pre-release status, the affected and fixed MCP/Pillow versions, validation evidence, and the statement that Torch 2.13 is out of scope. Do not claim registry publication.

- [x] **Step 2: Run focused quality checks**

Run:
```bash
cd fovux-mcp
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy --strict --warn-unused-ignores src/fovux
uv run pytest -x --no-header -q --basetemp=/tmp/fovux-kit-126-pytest
cd ..
python3 scripts/lint_docs_code.py .
python3 scripts/check_versions.py
python3 scripts/check_docs_truth.py
```
Expected: all commands exit 0.

- [x] **Step 3: Review the final diff**

Run:
```bash
git diff --check
git diff --stat
git diff -- fovux-mcp/pyproject.toml fovux-mcp/uv.lock docs/release-notes/1.4.1.md
```
Expected: only the two dependency floors, corresponding lock entries, plan, OSV policy, and release-note evidence are changed; Torch remains unchanged.

- [x] **Step 4: Commit the remediation**

Run:
```bash
git add .github/workflows/security.yml \
  docs/superpowers/plans/2026-07-20-issue-126-security-dependencies.md \
  fovux-mcp/pyproject.toml fovux-mcp/uv.lock fovux-mcp/osv-scanner.toml \
  fovux-mcp/tests/contract/test_mcp_protocol.py docs/release-notes/1.4.1.md
git commit -m "fix(security): remediate MCP and Pillow advisories"
```
Expected: one focused maintainer remediation commit on top of the preserved Dependabot commit; the pull request body references issue #126.
