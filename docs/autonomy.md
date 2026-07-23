# Repository Autonomy

This repository is maintained autonomously to meet high standards of CI/CD, security, and repository hygiene.

- Workflows live in `.github/workflows` and run from the `oaslananka/fovux-kit` repository.
- `oaslananka/fovux-kit` is the canonical source repository for code, issues, pull requests, CI,
  releases, and registry publishing.
- Code changes are validated via `pre-commit`; `task verify:required` is the canonical local
  pre-merge aggregate for deterministic credential-free required gates.
- Publishing credentials are stored in protected GitHub Actions secrets and injected at runtime.
- Automated release drafting, issue labeling, PR sizing, and branch cleanups are set up.
