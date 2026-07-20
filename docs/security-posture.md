# Fovux Security Posture Report

Generated on: 2026-07-20 16:27:58 UTC

## Summary
- **Visibility:** Public
- **Secret Scanning:** Enabled
- **Secret Scanning Push Protection:** Enabled
- **Dependabot Security Updates:** Enabled

## Branch & Tag Protection Rulesets
- **main-ci-solo-maintainer:** Enforcement `active`
  - Deletion prevented: Yes
  - Linear history required: Yes
  - Commit signatures required: No
  - Required status checks:
    - `ci-required`
    - `security-required`
    - `dependency-review`
    - `codeql-required`
- **release-tag-protection:** Enforcement `active`
  - Tag deletion prevented: Yes
  - Tag non-fast-forward prevented: Yes

## Dependabot Alerts Summary
- **Total Open Alerts:** 2
  - **Critical:** 0
  - **High:** 1
  - **Medium:** 0
  - **Low:** 1

## Deployment Environments
- **copilot:** No protection rules
- **github-pages:** Protected
- **npm-production:** No protection rules
- **production:** No protection rules
- **pypi-production:** No protection rules
- **vsce-production:** No protection rules

## Governance & Security Workflows
- Security workflow (.github/workflows/security.yml): Present
- CodeQL workflow (.github/workflows/codeql.yml): Present
- Scorecard workflow (.github/workflows/scorecard.yml): Present
- Python SPDX SBOM generator: Present
- Node.js SPDX SBOM generator: Present

