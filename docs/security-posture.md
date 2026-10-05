# Fovux Security Posture Report

Generated on: 2026-10-05 10:15:00 UTC

## Summary
- **Visibility:** Public
- **Secret Scanning:** Unavailable
- **Secret Scanning Push Protection:** Unavailable
- **Dependabot Security Updates:** Unavailable

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
    - `elevated-review-required`
- **release-tag-protection:** Enforcement `active`
  - Tag deletion prevented: Yes
  - Tag non-fast-forward prevented: Yes

## Dependabot Alerts Summary
- **Total Open Alerts:** Unavailable to current token

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
