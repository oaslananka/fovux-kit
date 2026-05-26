# Branch Protection

Ruleset is defined in `.github/rulesets/main.json`. 
Apply commands:
```bash
gh api -X POST /repos/oaslananka/fovux/rulesets --input .github/rulesets/main.json
gh api -X POST /repos/oaslananka-lab/fovux/rulesets --input .github/rulesets/main.json
```
Make sure to fill in the `required_status_checks` array inside the JSON file with the actual checks before applying, if you want strict required status checks.
