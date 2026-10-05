Fixed the security posture drift by reconciling `.github/rulesets/main.json` with the live `main-ci-solo-maintainer` ruleset.

## Changes Made

1. **`.github/rulesets/main.json`** - Added missing `require_extra_approval_for_unattributed_changes: true` parameter to the pull_request rule. This field was present in the live ruleset but missing from the tracked file, causing the strict posture check to report "live policy differs".

2. **`docs/security-posture.md`** - Regenerated to reflect current live policy:
   - Updated timestamp
   - Added `elevated-review-required` to required status checks (was already in tracked file but missing from old report)
   - Security scanning/Dependabot statuses shown as "Unavailable" (requires authenticated token, per script's fallback behavior)

## Verification

- Normalized tracked policy now matches normalized live policy exactly
- `_main_ruleset_deviations()` returns empty list (no drift)
- `git diff --check` passes (no whitespace issues)

The live ruleset (source of truth) is preserved faithfully — no enforcement was weakened. The `require_extra_approval_for_unattributed_changes: true` setting strengthens review requirements for unattributed commits.
