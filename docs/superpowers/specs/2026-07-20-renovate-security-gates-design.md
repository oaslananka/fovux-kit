# Renovate and Layered Developer Security Gates Design

**Date:** 2026-07-20  
**Issues:** #137, #138  
**Status:** Approved design, implementation pending

## 1. Purpose

Fovux Kit needs dependency automation and developer-facing security feedback that are reliable,
project-specific, and compatible with the existing protected-branch model. The solution must avoid
three common failure modes:

1. a Renovate configuration that exists but is never executed;
2. multiple dependency bots opening overlapping pull requests;
3. slow or credential-dependent scanners blocking every local commit.

The design uses a layered model: deterministic offline checks at commit time, credential-aware
checks at push or manual time, and authoritative full-repository gates in GitHub Actions and the
existing hosted security services.

## 2. Scope

### In scope

- replace the one-line Renovate inheritance with an explicit Fovux-specific configuration;
- validate the resolved Renovate configuration and prove the central runner can discover the repo;
- define ownership boundaries between Renovate and GitHub Dependabot security updates;
- add repository-owned Semgrep rules and a fast pre-commit scan;
- add full Semgrep scanning to the required security workflow;
- integrate Snyk and SonarQube Cloud into the pre-commit framework as credential-aware pre-push or
  manual hooks;
- add Taskfile entry points, documentation, validation scripts, and CI checks for the new controls;
- ensure generated reports and local credentials are never committed.

### Out of scope

- replacing CodeQL, Trivy, OSV Scanner, pip-audit, npm audit, pnpm audit, Gitleaks, or the existing
  hosted Snyk and SonarQube Cloud PR integrations;
- automatic merging of major runtime, protocol, computer-vision, or ML framework upgrades;
- storing Snyk, Sonar, GitHub App, or Renovate tokens in repository files;
- making authenticated cloud scanners mandatory for unaffiliated contributors;
- broad source-code refactoring unrelated to dependency or security automation.

## 3. Architecture

The solution has four independent layers.

### 3.1 Layer A: Commit-time deterministic checks

`pre-commit` remains the local orchestrator. The normal `pre-commit` stage will run only checks that
are deterministic, offline after hook installation, and fast enough for repeated use.

The new Semgrep hook will:

- use a pinned Semgrep version;
- scan only staged Python, TypeScript, TSX, and JavaScript files;
- load repository-owned rules from `.semgrep/rules/`;
- exclude lockfiles, generated bundles, coverage, build output, virtual environments, fixtures, and
  vendored content;
- fail only on findings explicitly classified as `ERROR` by the repository rule set;
- disable telemetry and metrics for local execution;
- target a normal execution budget below 15 seconds for a typical small commit.

The existing formatting, Ruff, Gitleaks, Actionlint, YAML, Markdown, and conventional-commit hooks
remain unchanged unless validation proves an incompatibility.

### 3.2 Layer B: Pre-push and manual authenticated checks

Snyk and SonarQube Cloud require credentials and network access. They will not run during every
commit.

Two local wrapper scripts will expose predictable behavior:

- `scripts/run_snyk.py` runs Snyk Open Source and Snyk Code with a `high` severity threshold;
- `scripts/run_sonar.py` runs SonarScanner for an explicitly requested branch or pull-request
  analysis.

Both wrappers will:

- verify that the required executable and token are available;
- print a clear command for configuring missing credentials;
- redact tokens and avoid echoing secret-bearing command lines;
- propagate scanner exit codes when an authenticated scan starts;
- write temporary output outside the repository or to ignored paths;
- distinguish `not configured locally` from `scan passed`.

The Snyk hook will run at `pre-push` only for maintainers who have `SNYK_TOKEN`; contributors without
credentials will receive an explicit local skip while the existing hosted Snyk PR check remains the
authoritative cloud result. The Sonar hook will be `manual` by default because a Sonar analysis
uploads repository-wide state and is not suitable for every push. It will be invokable through both
Taskfile and pre-commit manual stages.

### 3.3 Layer C: Authoritative CI gates

The existing `Security Scanning` workflow remains the aggregate security gate. A Semgrep job will be
added to it and included in `security-required`.

The CI Semgrep job will:

- use a pinned Semgrep CLI or container image;
- scan the complete relevant source tree;
- combine repository-owned rules with a reviewed set of Semgrep Registry rules for Python,
  TypeScript, and security audit coverage;
- emit SARIF;
- upload SARIF to GitHub code scanning using the already granted `security-events: write`
  permission;
- fail the security aggregate on blocking findings or scanner failure;
- avoid scanning dependencies, generated files, and lockfiles as source code.

Snyk and SonarQube Cloud will continue to run through their existing GitHub integrations. The repo
will not add duplicate token-backed CI jobs unless the hosted integrations become unavailable or
cannot enforce the intended severity policy. Their visible PR checks remain independent evidence;
`security-required` continues to be based only on repository-controlled jobs.

### 3.4 Layer D: Dependency automation

The repository `renovate.json` will explicitly extend:

```json
"github>oaslananka/.github:renovate-config"
```

and add Fovux-specific policy. The local configuration will enable only the managers needed by this
monorepo:

- `pep621` for `fovux-mcp`, including `pyproject.toml` and `uv.lock`;
- `npm` for `fovux-studio` and `fovux-mcp-npm`;
- `github-actions`;
- `dockerfile`;
- `nvm` for `.nvmrc`;
- `pre-commit`, explicitly enabled because that Renovate manager is not enabled by default.

The configuration will identify the repository as a three-component monorepo and assign existing
labels only. It must not depend on labels absent from `.github/labels.yml`.

## 4. Renovate Policy

### 4.1 Scheduling and pull-request volume

- timezone: `Europe/Istanbul`;
- vulnerability remediation: immediate;
- lockfile maintenance: before 06:00 on Monday;
- normal minor and patch updates: weekly maintenance window;
- major updates: dependency-dashboard approval required;
- maximum two new PRs per hour and six concurrent repository PRs;
- no broad package automerge;
- digest-only automerge may remain enabled only when all required branch checks pass and the update
  does not belong to a protected runtime group.

### 4.2 Protected dependency groups

The following groups always require maintainer review and never automerge:

1. **MCP protocol stack** — `mcp`, `fastmcp`, and closely coupled transport packages;
2. **YOLO and PyTorch stack** — `torch`, `torchvision`, `ultralytics`, CUDA-related packages, and
   platform-specific ML wheels;
3. **Computer-vision runtime stack** — `numpy`, `pillow`, `opencv-python-headless`, `onnx`, and
   `onnxruntime` when updated together or across compatibility boundaries;
4. **Studio runtime stack** — React, Vite, VS Code API types, extension packaging, and test runtime
   majors;
5. **Node and Python support policy** — `.nvmrc`, `@types/node`, Python classifiers, and declared
   minimum runtime versions;
6. **Release and security tooling** — release-please, CodeQL, Trivy, OSV Scanner, Gitleaks, Semgrep,
   Snyk, SonarScanner, and pre-commit framework majors.

Security patches may bypass the normal maintenance schedule but still require checks. A security PR
must never silently expand into an unrelated major framework upgrade.

### 4.3 Dependency-bot ownership

Fovux currently has GitHub Dependabot security updates enabled at repository level and no
`.github/dependabot.yml` version-update schedule. The initial ownership model is:

- Renovate owns routine version updates, grouping, lockfile maintenance, pre-commit hook updates,
  GitHub Actions updates, Docker base images, and dependency-dashboard workflow;
- GitHub Dependabot remains enabled for GitHub-native security alerts until Renovate has completed a
  successful lookup dry-run and a real scheduled run;
- duplicate security PRs are closed in favor of the PR that covers the complete remediation and
  passes the required gates;
- after two successful Renovate cycles, maintainers review whether Renovate vulnerability alerts
  should replace Dependabot security PR creation; GitHub alerting itself remains enabled either way.

This phased ownership prevents a configuration mistake from leaving the repository without a
security-update source.

## 5. Renovate Activation

The shared `oaslananka/.github` repository contains the central configuration and a manual Renovate
workflow, but no successful run has been recorded. Repository configuration alone is therefore not
considered activation.

Activation requires the following evidence:

1. a dedicated `RENOVATE_TOKEN` from a GitHub App installation token or appropriately scoped bot PAT;
2. a lookup-only dry-run against `oaslananka/fovux-kit` with config validation enabled;
3. log evidence that all intended managers and package files are discovered;
4. creation or update of the `Dependency Dashboard` issue;
5. one non-dry scheduled or manually dispatched run;
6. a branch or PR proving that required CI workflows are triggered by the bot identity.

The standard workflow `GITHUB_TOKEN` must not be used as the Renovate platform token because bot
commits created with that token may not trigger the repository workflows required by the main
ruleset.

The central workflow will remain manual until token validation and lookup dry-run succeed. It may
then receive a schedule. Activation credentials are an operational prerequisite and are never
committed to Fovux Kit.

## 6. Repository-Owned Semgrep Rules

The initial local rule set will be intentionally small and high-confidence.

### Python rules

- block `subprocess` calls with `shell=True` unless the line carries a documented, reviewed nosec
  suppression;
- block `eval`, `exec`, and unsafe dynamic code loading in production source;
- block unsafe YAML loading APIs;
- flag new subprocess launches that concatenate untrusted tool arguments;
- flag obvious path-boundary bypasses in HTTP and tool invocation adapters.

### TypeScript rules

- block `child_process.exec` with interpolated input;
- flag webview HTML assignment that omits the repository nonce/CSP helper;
- block unsafe `eval` and `new Function` usage;
- flag token or bearer credential logging.

Rules must include positive and negative fixtures. A rule is promoted to blocking only after its
fixtures pass and it produces no unexplained finding on the current repository. Noisy registry
rules may run in CI as warnings before they become blocking.

## 7. Configuration and Files

Expected implementation files:

- `renovate.json` — explicit shared preset plus Fovux package rules;
- `.pre-commit-config.yaml` — Semgrep pre-commit and credential-aware manual/pre-push hooks;
- `.semgrep.yml` and `.semgrep/rules/*.yml` — local configuration and rules;
- `.semgrep/tests/` — positive and negative rule fixtures;
- `scripts/run_snyk.py` — authenticated Snyk wrapper;
- `scripts/run_sonar.py` — authenticated SonarScanner wrapper;
- `scripts/validate_renovate_config.py` — static project-specific policy validation;
- `sonar-project.properties` — repository paths, exclusions, and report locations;
- `.github/workflows/security.yml` — Semgrep job and aggregate result;
- `Taskfile.yml` — `security:semgrep`, `security:snyk`, `security:sonar`, and combined developer
  entry points;
- `.gitignore` — scanner caches, reports, and temporary files;
- developer and security documentation describing installation, credentials, commands, and CI
  authority.

Implementation may consolidate wrappers when doing so keeps token handling and exit semantics clear.

## 8. Secrets and Data Handling

- `SNYK_TOKEN`, `SONAR_TOKEN`, and `RENOVATE_TOKEN` are read from the environment or GitHub secret
  store only;
- `.env` remains ignored and must never be printed by wrappers;
- scanner subprocess calls use argument arrays rather than shell interpolation;
- local SARIF, scanner cache, and report directories are ignored;
- no scanner is allowed to upload source without an explicit authenticated command or the existing
  documented GitHub integration;
- Semgrep local execution disables metrics;
- logs redact tokens, Authorization headers, and authenticated URLs.

## 9. Error Handling

### Renovate

- invalid local config fails validation and CI;
- missing central token prevents activation and leaves the workflow manual;
- manager discovery mismatches fail the lookup acceptance check;
- unknown or missing labels fail project-specific validation before activation;
- a bot PR that does not trigger required checks is not mergeable and blocks scheduled activation.

### Semgrep

- syntax errors, invalid rules, and scanner crashes fail both local hook and CI;
- local findings are printed with file and rule identifiers;
- CI always attempts SARIF upload when a SARIF file exists;
- registry network failures fail CI rather than silently reducing coverage.

### Snyk and Sonar

- missing local credentials produce an explicit `not configured` result, not a false pass;
- authenticated scanner failures propagate a non-zero exit code;
- CI authority remains the existing hosted PR integration unless a repository-controlled job is
  later added;
- wrappers never downgrade a genuine scanner failure to a skip.

## 10. Testing Strategy

### Renovate tests

- parse and schema-validate `renovate.json`;
- assert the explicit shared preset reference;
- assert required managers and monorepo paths;
- assert protected dependency groups have `automerge: false`;
- assert all configured labels exist in `.github/labels.yml`;
- run Renovate `--platform=local --dry-run=lookup` or equivalent config validation where possible;
- capture a central lookup dry-run proving manager and package discovery.

### Semgrep tests

- use `semgrep --test` for every local rule;
- run the staged-file hook against representative safe and unsafe fixtures;
- run the complete repository configuration and establish a zero-unreviewed-finding baseline;
- validate SARIF generation and upload configuration;
- verify `security-required` fails when the Semgrep job fails or is skipped unexpectedly.

### Wrapper tests

- unit-test missing executable, missing token, successful subprocess, failed subprocess, and token
  redaction paths;
- assert command construction uses argument arrays;
- assert reports are written only to ignored paths;
- verify Taskfile and pre-commit commands call the same wrappers.

### Regression verification

The complete backend and Studio test suites, pre-commit hooks, Actionlint, documentation checks,
security scans, and Renovate policy validation must pass before the implementation PR is ready.

## 11. Rollout

1. merge the current security remediation and governance work;
2. add and validate Fovux-specific Renovate configuration without enabling scheduled mutation;
3. add Semgrep rules, local hook, CI job, SARIF upload, and aggregate gate;
4. add credential-aware Snyk and Sonar wrappers plus Taskfile/manual hook integration;
5. run the central Renovate lookup-only dry-run;
6. configure the dedicated Renovate token outside the repository;
7. execute one real manual Renovate run and verify the resulting PR receives all required checks;
8. enable the central schedule;
9. observe two successful cycles before changing vulnerability-PR ownership.

Rollback is component-specific: disable the scheduled Renovate workflow without removing repository
config, remove Semgrep from the aggregate only when the job itself is broken, and leave hosted Snyk
and Sonar checks intact throughout.

## 12. Acceptance Criteria

### Issue #137

- the repository has explicit, schema-valid Fovux-specific Renovate policy;
- intended managers discover all Python, npm/pnpm, GitHub Actions, Docker, Node, and pre-commit files;
- protected dependency groups cannot automerge;
- configured labels exist;
- central lookup dry-run succeeds;
- a dedicated bot credential is used;
- Dependency Dashboard and one real Renovate PR prove activation and CI triggering;
- bot ownership and rollback are documented.

### Issue #138

- local Semgrep rules have passing positive and negative fixtures;
- Semgrep runs in normal pre-commit and in the required security workflow;
- CI emits and uploads SARIF;
- Snyk is available through credential-aware pre-push and manual commands;
- SonarScanner is available through a credential-aware manual command;
- missing local credentials are explicit skips rather than false passes;
- authenticated failures block the invoking command;
- all scanner secrets and outputs are handled according to Section 8;
- existing CodeQL, Trivy, OSV, audit, hosted Snyk, and hosted Sonar controls remain operational.
