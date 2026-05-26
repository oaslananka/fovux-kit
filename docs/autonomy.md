# Repository Autonomy

This repository is maintained autonomously to meet high standards of CI/CD, security, and repository hygiene.
- Workflows live in `.github/workflows` and are guarded to only run in the `oaslananka-lab/fovux` mirror.
- `oaslananka/fovux` is the canonical source repository with Actions disabled.
- `oaslananka-lab/fovux` runs CI/CD and mirrors release refs/assets back to the
  canonical repository with `MIRROR_PAT`.
- Code changes are validated via `pre-commit` and `task ci`.
- Secrets are centralized in Doppler and injected at runtime.
- Automated release drafting, issue labeling, PR sizing, and branch cleanups are set up.
