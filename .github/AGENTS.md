# GitHub Automation Instructions

These instructions apply to `.github/**` and supplement the root instructions.

Workflow changes alter CI governance, security scanning, protected publishing, release evidence, marketplace authority or branch protection.

## Required checks and CI

- Preserve required aggregate contexts such as quality/compatibility/security gates unless branch protection is intentionally migrated.
- Do not use `continue-on-error`, path filters, skip logic, threshold changes or exclusions to hide a repository-owned failure.
- Draft/ready-for-review routing must remain consistent with the documented CI skip policy.
- Third-party Actions remain pinned to reviewed full commit SHAs.

## Permissions and secrets

- Keep default workflow permissions minimal.
- Grant write or OIDC only to the smallest reviewed job.
- Pull-request code must not receive PyPI, npm, Marketplace, Open VSX, signing, Doppler, Sonar or other protected credentials.
- Protected environments remain the authority for publication and sensitive operations.

## Release

- Release Please owns version proposals.
- Keep Python, npm wrapper and Studio publication sequencing/version contracts aligned with the repository release docs.
- Preserve checksums, SBOMs, provenance/attestations, package-content verification and post-publish checks.
- Do not publish locally or from an unprotected PR path.
- Released tags/artifacts are immutable.

## Security

Gitleaks, Semgrep, Trivy, pip-audit, pnpm/npm audit, OSV and posture checks are evidence gates. Do not weaken severity, routing or required aggregate behavior to land unrelated work.

## Verification

Workflow edits require actionlint/Zizmor plus the repository release/security/required-gate validators. YAML parsing alone is not sufficient evidence.
