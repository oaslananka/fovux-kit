# Quality Observability

Fovux Kit uses one tool per primary responsibility:

- **Codecov** reports Python and TypeScript coverage, patch impact, and failed-test analytics.
- **SonarQube Cloud** remains the maintainability, reliability, duplication, and security-hotspot quality gate.
- **CodeQL** is the primary general SAST gate; repository-owned Semgrep rules enforce Fovux-specific patterns.
- **actionlint + zizmor** validate GitHub Actions syntax and security.

## Codecov rollout

The Linux quality lane uploads backend XML coverage, Studio LCOV coverage, and JUnit results once per commit. Compatibility cells do not upload reports. Upload authentication uses GitHub OIDC, so no long-lived `CODECOV_TOKEN` is stored. The Codecov GitHub App must have repository access.

Project and patch targets track the base automatically with a 1% tolerance. During rollout, Codecov statuses are informational so Sonar and the existing 85% local coverage thresholds are not duplicated as independent merge gates. After a stable default-branch baseline exists, maintainers may promote Codecov checks deliberately.

## Bundle analysis

Studio already has a deterministic `check:bundle-size` gate. Codecov Bundle Analysis is configured as informational only. The repository uses tsup/esbuild rather than a directly supported Vite/Rollup/Webpack plugin path; a remote bundle upload should only be enabled after Codecov tokenless or OIDC support is verified for the generic bundle analyzer.

## Failed-test reporting

Pytest and Vitest emit JUnit XML. Upload steps run when tests fail, unless the workflow is cancelled, so Codecov can annotate failed and flaky tests without weakening the final required quality result.
