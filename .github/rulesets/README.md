# Repository Rulesets

These JSON files mirror the repository rulesets that should be applied through
the GitHub REST API or the repository settings UI.

## `main-protection`

`main.json` targets the default branch with:

- branch deletion protection
- force-push protection
- required linear history
- verified commit signatures
- pull requests required before updates to `main`
- resolved review threads required before merge
- required status checks:
    - `ci-required`
    - `security-required`
    - `codeql-required`
    - `scorecard-required`
    - `release-please`

The repository currently has one administrator and no separate reviewer pool.
For that reason, the exported ruleset requires pull requests and review-thread
resolution, but sets `required_approving_review_count` to `0` and disables code
owner and last-push approval requirements. When another maintainer or reviewer
team is added, raise the approval count to `1`, enable code owner review, and
enable last-push approval.

## `release-tag-protection`

`release-tags.json` targets release tag patterns and blocks deletion and
non-fast-forward updates for released tags.

## Applying

Create a missing ruleset with:

```powershell
gh api --method POST repos/{owner}/{repo}/rulesets --input .github/rulesets/main.json
gh api --method POST repos/{owner}/{repo}/rulesets --input .github/rulesets/release-tags.json
```

Update an existing ruleset with:

```powershell
gh api --method PUT repos/{owner}/{repo}/rulesets/{ruleset_id} --input .github/rulesets/main.json
gh api --method PUT repos/{owner}/{repo}/rulesets/{ruleset_id} --input .github/rulesets/release-tags.json
```

After applying, verify:

```powershell
gh api repos/{owner}/{repo}/rulesets --jq "map({id,name,enforcement,target})"
gh api repos/{owner}/{repo}/rules/branches/main --jq "map({type,ruleset_source_type,ruleset_source,ruleset_id})"
```
