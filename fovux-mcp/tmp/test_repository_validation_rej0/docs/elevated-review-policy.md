# Elevated Pull Request Review Policy

The repository keeps the blanket approving-review count at zero for the solo-maintainer model, but
high-risk changes must pass the `elevated-review-required` commit status before merge. The gate runs
from trusted default-branch code through `pull_request_target`, checks out only the pull request's
base SHA, and evaluates GitHub metadata; it never checks out or executes pull-request head code.

The ruleset activation phase is `active`. The workflow is installed on `main`, and
`elevated-review-required` is required by both the tracked and live branch ruleset. Repository drift
checks fail if the policy phase, tracked context, live context, or public documentation diverges.

## Elevated classification

A pull request is elevated when any configured label or immutable changed path matches. The label
set is `risk:high`, `size/XL`, and `requires-review`. Labels are not the only signal: changed-file
classification remains authoritative even when labels are removed or changed.

Sensitive path categories are:

- `authentication-authorization`: authentication, authorization, and path-policy controls;
- `subprocess-execution`: process spawning and command execution boundaries;
- `workflow-permissions`: GitHub workflows, rulesets, CODEOWNERS, and this policy;
- `release-publishing`: package publishing, release automation, registry verification, and baseline updates;
- `registry-schema-migration`: tool/run registries, public schemas, migrations, and Alembic state.

Routine low-risk documentation and maintenance changes that match neither a label nor a sensitive
path pass automatically and are not forced through the elevated process.

## Required independent checks

Every elevated decision is bound to the current head SHA and waits for all of these checks:

- `ci-required`;
- `security-required`;
- `dependency-review`;
- `codeql-required`;
- `Review Threads`.

A failed required check publishes a failed elevated status. A missing or pending check publishes a
pending status until the pull request body is edited after all checks finish. Any unresolved review
thread also keeps the status pending. Bot/agent, security, coverage, and reviewer findings must
therefore be resolved or explicitly dispositioned before the final evidence update.

## Evidence in the pull request body

After required checks, bot/agent reports, and reviews complete, edit the pull request body and fill
this exact structured block:

```markdown
<!-- elevated-review-evidence -->

Head SHA: <40-character current head SHA>
Reviewer: @<reviewer login>
Risk assessment: <what can fail and why the change is elevated>
Validation evidence: ci-required, security-required, dependency-review, codeql-required, Review Threads <results>
Bot/agent findings: <SonarQube, Codecov, CodeQL, Semgrep, Socket, DeepScan, and review findings or rationale>
Residual risk: <remaining risk and rollback path>
```

Empty placeholders such as `None`, `N/A`, `TBD`, or `Pending` are rejected. The `edited`
`pull_request_target` event reruns the gate using trusted base-branch code. A new push changes the
current head SHA, invalidates the prior body evidence, and requires another edit after the new checks
finish.

## solo-maintainer path

For a maintainer-authored pull request, GitHub does not permit self-approval. The repository accepts
the public, structured, current-head body evidence only when `Reviewer` matches the pull-request
author, independent required checks pass, and all threads are resolved. This is not silent
self-certification: risk analysis, validation results, bot/agent disposition, residual risk,
reviewer identity, and exact current head SHA remain in the public pull-request audit trail.

## external-contributor path

For an external-contributor pull request, structured body evidence is necessary but not sufficient.
The named reviewer must have `OWNER`, `MEMBER`, or `COLLABORATOR` association and must submit an
`APPROVED` review on the current head SHA. Stale, dismissed, author-self, or unauthorized approvals
do not count. After approval and all required checks finish, edit the pull request body to rerun the
gate with the final evidence.

## Safe workflow model

The workflow uses `pull_request_target` because a normal `pull_request` workflow is loaded from the
pull-request merge branch and can therefore be modified by the same pull request whose evidence it
is meant to enforce. The target workflow is a **base-only metadata gate**: it checks out
`${{ github.event.pull_request.base.sha }}`, persists no credentials, never fetches pull-request head
content, and passes no attacker-controlled string into shell commands.

The trigger has an explicit, reviewable Zizmor suppression:
`# zizmor: ignore[dangerous-triggers] base-only metadata gate; never executes pull-request code`
annotation. This suppression is accepted only with the exact safety contract above and is enforced
by repository drift tests. The workflow does not use `workflow_run`, issue-comment triggers,
review-comment triggers, `refs/pull`, `github.head_ref`, or `gh pr checkout`.

Permissions are limited to read access for `contents`, `pull-requests`, and `checks`, plus
`statuses: write`. The write permission is used only to publish `elevated-review-required` on the
current pull-request head SHA. The workflow job itself exits successfully after publishing a
`success`, `pending`, or `failure` decision; the custom commit status is the ruleset signal.

Repository drift is checked with:

```bash
python scripts/check_review_evidence.py --validate-repository
```

The check synchronizes policy JSON, workflow safety constraints, pull-request template, this public
policy, branch-protection documentation, Taskfile wiring, existing required checks, approval count,
thread resolution, bypass actors, and the `bootstrap`/`active` ruleset phase.
