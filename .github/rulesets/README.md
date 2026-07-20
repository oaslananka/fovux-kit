# Repository Rulesets

These JSON files are the canonical repository ruleset request payloads. Apply them through the
GitHub REST API and use `scripts/generate_security_posture.py --strict` to detect semantic drift
between the tracked main policy and the live repository configuration.

## `main-ci-solo-maintainer`

`main.json` targets `refs/heads/main` with:

- branch deletion protection;
- force-push protection;
- required linear history;
- pull requests required before updates to `main`;
- resolved review threads required before merge;
- strict required status checks:
  - `ci-required`;
  - `security-required`;
  - `dependency-review`;
  - `codeql-required`;
- no bypass actors.

The repository currently has one administrator and no independent reviewer pool. Therefore, the
policy requires pull requests and resolved review threads but sets the mandatory approval count to
`0`; code-owner and last-push approval are disabled. Add those reviewer controls when a second
maintainer or reviewer team is available.

Signed commits are not required by this ruleset because contributor signing setup has not yet been
standardized. `scorecard-required` and `release-please` remain visible checks but are not merge
requirements: their event coverage and release-only behavior do not provide the same stable PR gate
contract as the four aggregate checks above.

## `release-tag-protection`

`release-tags.json` targets the release tag patterns and blocks deletion and non-fast-forward
updates. It does not block initial tag creation by release automation.

## Applying

Discover the existing ruleset IDs first:

```bash
gh api repos/{owner}/{repo}/rulesets --jq 'map({id,name,enforcement,target})'
```

Update the existing main ruleset rather than creating a duplicate:

```bash
gh api --method PUT repos/{owner}/{repo}/rulesets/{main_ruleset_id} \
  --input .github/rulesets/main.json
```

Create the release tag ruleset when it is missing:

```bash
gh api --method POST repos/{owner}/{repo}/rulesets \
  --input .github/rulesets/release-tags.json
```

After applying, verify:

```bash
gh api repos/{owner}/{repo}/rulesets --jq 'map({id,name,enforcement,target})'
gh api repos/{owner}/{repo}/rules/branches/main \
  --jq 'map({type,ruleset_source_type,ruleset_source,ruleset_id})'
python3 scripts/generate_security_posture.py --strict
```
