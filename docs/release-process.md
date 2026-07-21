# Release Process

Releases are automated from merges to `main` in `oaslananka/fovux-kit`.

1. A maintainer merges a normal pull request with Conventional Commits.
2. `release-please` evaluates commit history and updates package version files plus package changelogs in one grouped release pull request.
3. A maintainer reviews and merges the release pull request.
4. The release workflow creates the GitHub Release from release-please outputs.
5. Publish jobs build artifacts on GitHub-hosted runners, generate SBOMs and SHA256 checksums, attest provenance, attach assets, publish to registries, and verify the release.
6. After registry verification, synchronize the reviewed published baseline through a normal pull request.


## Release Evidence Checklist

A GitHub Release is not considered verified until its notes or attached artifacts document:

- package versions for every released track;
- VSIX packaging status plus VS Marketplace and Open VSX publication status when Studio is released;
- SBOM, SHA256 checksum, and provenance/attestation assets;
- registry verification evidence JSON;
- PyPI, npm, Marketplace, and Open VSX smoke-test or metadata-check results for the channels that were released;
- any skipped channel, external blocker, or manual recovery action.

Version numbers are never supplied manually during the normal release path. The
verified first-public `1.0.0` release is complete, so release-please calculates
subsequent versions from Conventional Commits. The Python `fovux-mcp` package
and npm wrapper are linked; `fovux-studio` remains an independent release track.
Release tags remain component-specific for the monorepo packages.

## Post-release baseline synchronization

After the `Verify Release` job succeeds, update the machine-readable baseline using the versions
reported by release-please and the verified registry evidence:

```bash
python scripts/update_release_baseline.py
python scripts/check_release_truth.py
python scripts/check_docs_truth.py
```

Commit the generated `release-baseline.json`, README, ROADMAP, and release-note changes through a
normal pull request. Historical release-note files for earlier versions must remain unchanged.
