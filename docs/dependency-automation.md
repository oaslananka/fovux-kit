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

Routine updates run in the Monday 02:00–06:00 Europe/Istanbul maintenance window. Vulnerability
remediation remains immediate. The repository allows at most two new Renovate pull requests per hour
and six concurrent Renovate pull requests.

Major updates require Dependency Dashboard approval. MCP/FastMCP, Torch/YOLO/CUDA, computer-vision
runtime, Studio runtime, Node support-policy, and release/security tooling updates never automerge.
Required branch checks still apply to every bot pull request.

## Bot ownership

Renovate owns routine version updates, grouping, lockfile maintenance, GitHub Actions, Docker,
`.nvmrc`, and pre-commit hooks. GitHub Dependabot security updates remain enabled until Renovate has
completed both a successful lookup dry-run and a real run that creates a dashboard or pull request
whose commits trigger all required checks.

When duplicate security pull requests exist, retain the remediation that covers the complete affected
dependency set and passes `ci-required`, `security-required`, `dependency-review`, and
`codeql-required`.

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

The CI aggregate runs the deterministic validator. A central Renovate lookup dry-run is separate
activation evidence because it verifies remote preset resolution, repository discovery, and the bot
credential.

## Activation procedure

1. Store a dedicated GitHub App token or appropriately scoped bot PAT as `RENOVATE_TOKEN` in the
   central automation repository. Never use a repository workflow `GITHUB_TOKEN` for mutation.
2. Dispatch `oaslananka/.github` workflow `renovate-manual.yml` with `dryRun=true` and inspect manager
   discovery.
3. Confirm `pep621`, npm/pnpm, GitHub Actions, Dockerfile, NVM, and pre-commit package files are found.
4. Run once with `dryRun=false` and confirm the Dependency Dashboard or a Renovate PR is created.
5. Confirm the bot PR receives all required main checks.
6. Only after that evidence, add a schedule to the central workflow.
7. Observe two successful cycles before considering any change to security-PR ownership.

## Rollback

Disable the central schedule or revoke the dedicated Renovate credential. Keep `renovate.json` and
its validator so policy remains reviewable. Do not disable GitHub security alerting during rollback.
