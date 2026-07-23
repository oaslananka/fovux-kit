# Branch Protection

The canonical `main` ruleset is `.github/rulesets/main.json`. It is named
`main-ci-solo-maintainer`, targets `refs/heads/main`, uses strict status checking, and has no bypass
actors.

Required merge checks:

- `ci-required`;
- `security-required`;
- `dependency-review`;
- `codeql-required`;
- `elevated-review-required`.

The ruleset also blocks deletion and non-fast-forward updates, requires linear history, requires a
pull request, and requires every review thread to be resolved. The approval count remains `0` for
the current solo-maintainer model; that is not a bypass and does not waive required checks.

Apply changes to the existing ruleset ID:

```bash
gh api --method PUT repos/oaslananka/fovux-kit/rulesets/18689082 \
  --input .github/rulesets/main.json
```

Validate tracked/live equivalence:

```bash
python3 scripts/generate_security_posture.py --strict
```

The posture check continues ruleset validation when the workflow token cannot read the privileged
Dependabot alerts endpoint. Restricted alert access is reported as unavailable; it no longer turns
a ruleset drift failure into a false success.

## Elevated review evidence

The base-trusted `Elevated Review Evidence` workflow publishes the `elevated-review-required` commit
status for high-risk labels and immutable sensitive paths. The repository policy is now
`ruleset_activation: active`, and the context is required by both the tracked and live `main`
ruleset.

The approval count remains zero for the solo-maintainer model, but elevated changes require
current-head evidence in the pull request body, independent required checks, resolved threads,
and—on the external-contributor path—a current-head authorized approval. Editing the body after
checks and reviews finish reruns the base-only `pull_request_target` metadata gate.

The workflow's privileged trigger is constrained to base SHA checkout, no pull-request code
execution, no `workflow_run` or comment trigger, no persisted credentials, and a single
`statuses: write` capability. Its exact Zizmor suppression rationale is checked by repository drift
validation. See [Elevated Pull Request Review Policy](elevated-review-policy.md).
