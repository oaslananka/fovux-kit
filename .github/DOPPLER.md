# Doppler Secret Management

Fovux uses Doppler as the source of truth for CI and release secrets.

## Expected Secrets

The committed inventory lives in `.doppler/secrets.txt`. It contains secret names only:

- `DOPPLER_GITHUB_SERVICE_TOKEN`
- `OVSX_PAT`
- `PYPI_TOKEN`
- `VSCE_PAT`

The active release workflow uses a transitional GitHub Actions secret model:
Doppler project `all`, config `main` remains the inventory source of truth, and
the production registry secrets consumed by `.github/workflows/release-please.yml`
are synced into GitHub Actions environment or repository secrets. The only
registry secrets currently consumed by release jobs are `PYPI_TOKEN`, `VSCE_PAT`,
and `OVSX_PAT`. `MIRROR_PAT` is GitHub-only because it grants repository mirror
permissions rather than registry access.

## Add a New Secret

1. Add the value in Doppler project `all`, config `main`.
2. Add the secret name to `.doppler/secrets.txt` if CI or release jobs need it.
3. Sync the consumed secret into the matching GitHub Actions environment or
   repository secret before enabling a release job.
4. For local verification only, wrap consuming commands with:

   ```bash
   doppler run --project all --config main -- bash -lc 'task ci'
   ```

   ```powershell
   doppler run --project all --config main -- pwsh -NoProfile -Command 'task ci'
   ```

5. Verify with:

   ```bash
   bash scripts/verify_doppler_secrets.sh
   ```

Dashboard: https://dashboard.doppler.com/
