# Repository Operations

## Dual-owner repository model

This repository uses a dual-owner model:
- `oaslananka/fovux` is the canonical public repository. It consumes **zero** GitHub Actions minutes.
- `oaslananka-lab/fovux` is the protected CI/CD and release repository.

Changes land through reviewed pull requests. Direct branch replay and tag rewriting are intentionally disabled.
The two repositories must stay identical for branches, tags, releases, labels,
open issues, and open pull requests. Repository Parity runs in the org repo
every 30 minutes to detect drift.

`MIRROR_PAT` is required in `oaslananka-lab/fovux` for workflows that need to
write back to `oaslananka/fovux`, such as mirroring release commits, release
tags, and release assets after release-please publishes from the org repo.

## Disable Actions defensively on personal repo

```bash
# Disable Actions entirely on the personal repo
gh api -X PUT /repos/oaslananka/fovux/actions/permissions \
  -f enabled=false

# Re-enable later if needed:
gh api -X PUT /repos/oaslananka/fovux/actions/permissions \
  -f enabled=true -f allowed_actions=all
```

## Branch hygiene

The canonical repo should have "Automatically delete head branches" enabled:
```bash
gh api -X PATCH /repos/oaslananka/fovux -f delete_branch_on_merge=true
```

Use the branch hygiene report workflow to review old branches before deleting them.
