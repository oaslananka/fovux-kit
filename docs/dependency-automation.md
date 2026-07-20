# Dependency Automation

Fovux Kit uses a repository-specific Renovate policy layered on the shared
`oaslananka/.github:renovate-config` preset. The checked-in `renovate.json` is the source of truth
for this monorepo.

## Managed files

Renovate is limited to these manager families:

- `pep621` for `fovux-mcp/pyproject.toml` and `fovux-mcp/uv.lock`;
- `npm` for Studio pnpm files and the npm wrapper package lock;
- `github-actions` for workflow action references;
- `dockerfile` for the backend image;
- `nvm` for `.nvmrc`;
- `pre-commit` for pinned hook revisions.

`pep621` owns uv lock maintenance; there is no separate Renovate `uv` manager.

## Scheduling and review

Routine updates run in the Monday 02:00–06:00 Europe/Istanbul maintenance window. GitHub-native
Dependabot security updates remain immediate. The repository allows at most two new Renovate pull
requests per hour and six concurrent Renovate pull requests.

Major updates require Dependency Dashboard approval. MCP/FastMCP, Torch/YOLO/CUDA, computer-vision
runtime, Studio runtime, Node support-policy, and release/security tooling updates never automerge.
Required branch checks still apply to every bot pull request.

## Bot ownership

Renovate owns routine version updates, grouping, lockfile maintenance, GitHub Actions, Docker,
`.nvmrc`, and pre-commit hooks through the installed hosted Renovate GitHub App. Native Dependabot
security updates remain enabled and own vulnerability-remediation pull requests during the initial
rollout. Repository-local `vulnerabilityAlerts.enabled=false` and `osvVulnerabilityAlerts=false`
override the shared preset so the two bots cannot open duplicate security pull requests.

## Validation

The deterministic repository validator does not require network access:

```bash
python scripts/validate_renovate_config.py
```

The Renovate schema validator requires Node.js 24.11 or newer; `.nvmrc` is the supported local
runtime:

```bash
npm exec --yes --package=renovate@43.272.4 -- renovate-config-validator renovate.json
```

The CI aggregate runs the deterministic validator. The hosted Renovate GitHub App resolves the remote
preset and performs repository discovery; this repository does not store or require `RENOVATE_TOKEN`.

## Activation procedure

1. Keep the hosted Renovate GitHub App installed with access to `oaslananka/fovux-kit`.
2. Merge a schema-valid `renovate.json` change to the default branch so the hosted App reprocesses the
   repository.
3. Confirm the Dependency Dashboard is created and lists PEP 621/uv, npm/pnpm, GitHub Actions,
   Dockerfile, NVM, and pre-commit package files.
4. Confirm the first Renovate pull request receives `ci-required`, `security-required`,
   `dependency-review`, and `codeql-required`.
5. Observe two successful cycles before considering any change to security-PR ownership.

No repository or central-workflow token is needed for the hosted App path. The central manual workflow
is optional self-hosted infrastructure and is not part of Fovux activation.

## Rollback

Remove this repository from the hosted Renovate App installation or temporarily set `enabled: false`
in `renovate.json`. Keep the validator and GitHub security alerting enabled during rollback.
