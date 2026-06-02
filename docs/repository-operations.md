# Repository Operations

## Repository model

This repository uses a single public source-of-truth model:

- `oaslananka/fovux-kit` is the canonical public repository.
- GitHub Actions in `.github/workflows` run CI, security checks, release drafting, and publishing.
- Protected GitHub environments hold registry publishing credentials and approval gates.

Changes land through reviewed pull requests. Direct branch replay and tag rewriting are intentionally
disabled.

## Actions permissions

```bash
gh api -X PUT /repos/oaslananka/fovux-kit/actions/permissions \
  -f enabled=true -f allowed_actions=all
```

## Branch hygiene

The canonical repo should have "Automatically delete head branches" enabled:

```bash
gh api -X PATCH /repos/oaslananka/fovux-kit -f delete_branch_on_merge=true
```

Use the branch hygiene report workflow to review old branches before deleting them.
