# Supply-chain Verification

Fovux releases must minimize long-lived registry tokens and publish verifiable artifacts.

## Publishing policy

- PyPI publishing uses GitHub Actions OIDC / Trusted Publishing when configured for the `pypi-production` environment.
- PyPI token publishing is a guarded fallback only when trusted publishing is not yet configured.
- npm publishing uses trusted publishing/provenance-capable GitHub-hosted runners and `npm publish --provenance --access public`.
- Release jobs request `id-token: write` and provenance/attestation permissions only where needed.

## Evidence produced

- Python wheel and sdist.
- npm package tarball.
- VSIX package.
- SBOMs.
- SHA256 checksum files.
- GitHub build provenance attestations.
- Registry verification JSON reports.

## Consumer verification

1. Download the GitHub Release assets.
2. Check SHA256 files against downloaded artifacts.
3. Verify provenance/attestations from the GitHub release page or GitHub CLI.
4. Run `scripts/verify_registry_releases.py` for registry package checks.
5. Use `scripts/verify_signatures.sh` where Sigstore bundle assets are available.
## Registry verification evidence semantics

Registry evidence uses schema version 2. Step statuses are terminal `passed`, terminal `failed`,
intentional `skipped`, or non-terminal `retry`. Registry propagation polling can therefore record
multiple retries before one successful terminal observation without inflating the failure count. The
summary exposes `passed`, `failed`, `skipped`, and `retries` separately; only an exhausted final
attempt is counted as failed. Retry limits and delays remain workflow-controlled.
