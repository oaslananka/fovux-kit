# Branch Protection

The canonical `main` ruleset is `.github/rulesets/main.json`. It is named
`main-ci-solo-maintainer`, targets `refs/heads/main`, uses strict status checking, and has no bypass
actors.

Required merge checks:

- `ci-required`;
- `security-required`;
- `dependency-review`;
- `codeql-required`.

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
