## Implementation Complete

Aligned tracked ruleset names with live GitHub rulesets (`main-standard` and `release-tags`) as required by the diagnosis.

### Changes Made

| File | Change |
|------|--------|
| `.github/rulesets/main.json` | Ruleset name: `main-ci-solo-maintainer` → `main-standard` |
| `.github/rulesets/release-tags.json` | Ruleset name: `release-tag-protection` → `release-tags` |
| `scripts/generate_security_posture.py` | Updated discovery to look for `release-tags` |
| `fovux-mcp/tests/unit/test_security_posture_ruleset.py` | Updated test expectation to `main-standard` |
| `.github/rulesets/README.md` | Updated documentation headers |
| `docs/branch-protection.md` | Updated ruleset name reference |

### Verification

- All 5 unit tests pass (`test_security_posture_ruleset.py`)
- `git diff --check` — no whitespace issues
- `ruff check .` and `ruff format --check .` — all lint/format checks pass

Preserved all protection rules and strict failure behavior. Live policy drift remains visible for maintainer reconciliation.