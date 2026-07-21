# Release Process

Fovux uses a protected GitHub Actions release model.

| Repo                   | Role                                       |
| ---------------------- | ------------------------------------------ |
| `oaslananka/fovux-kit` | Source, CI, security gates, and publishing |

## Release Tracks

### fovux-mcp to PyPI

- Versioned from Conventional Commits through the grouped release-please PR on the org repository.
- Release artifacts are built from the tagged source.
- GitHub Release artifacts, SBOMs, checksums, and provenance are always attached
  first.
- The automatic publish path is `.github/workflows/release-please.yml`.
- `.github/workflows/publish-production.yml` is a manual recovery workflow and
  never races the automatic release publisher.
- PyPI publishing prefers trusted publishing when
  `PYPI_TRUSTED_PUBLISHING_ENABLED=true` and the PyPI trusted publisher matches
  `oaslananka/fovux-kit`, environment `pypi-production`, and
  `.github/workflows/publish-production.yml`.
- Until trusted publishing is configured, the guarded production job may use
  `PYPI_TOKEN` from the `pypi-production` environment. Only wheel and sdist
  files from the GitHub Actions runner are uploaded to PyPI.
- A package release fails closed when neither trusted publishing nor `PYPI_TOKEN`
  is available.

### fovux-mcp npm wrapper

- Published to npm as `fovux-mcp`.
- Versioned with the Python `fovux-mcp` package because the wrapper delegates CLI
  execution to the matching Python package version through `uvx`.
- npm publishing runs with provenance on GitHub-hosted runners. Trusted
  publishing can use GitHub Actions OIDC when configured for the package;
  otherwise `NPM_TOKEN` from the `npm-production` environment is required.

### fovux-studio to VS Marketplace and Open VSX

- Published as `oaslananka.fovuxstudiokit`; the extension keeps the `Fovux Studio` display name and
  stable `fovux.*` contribution identifiers.
- Versioned independently from `fovux-mcp` through its own release-please package entry.
- The release workflow packages the extension with the VS Code extension CLI.
- Marketplace publishing runs only when `VSCE_PAT` and `OVSX_PAT` are configured
  in the `vsce-production` environment or org repo secrets.

## Release Evidence Checklist

A GitHub Release is not considered verified until its notes or attached artifacts document:

- package versions for every released track;
- VSIX packaging status plus VS Marketplace and Open VSX publication status when Studio is released;
- SBOM, SHA256 checksum, and provenance/attestation assets;
- registry verification evidence JSON;
- PyPI, npm, Marketplace, and Open VSX smoke-test or metadata-check results for the channels that were released;
- any skipped channel, external blocker, or manual recovery action.

## Normal Release

1. Merge changes to `main` through a reviewed pull request.
2. CI, CodeQL, security scans, and review gates pass in this repository.
3. release-please opens one grouped release PR with version and changelog updates.
4. A maintainer reviews and merges the release PR.
5. Publish jobs run for each package that received a release.
6. SBOM, SHA256 checksum, and provenance assets are attached to the GitHub Release.
7. Run `scripts/update_release_baseline.py` after the package manifests contain the verified versions and merge the generated baseline update through a pull request.

## Emergency Hotfix

```bash
git checkout main
git pull
git checkout -b hotfix/critical-fix
# make changes
git commit -m "fix(mcp): critical bug description"
git push origin hotfix/critical-fix
gh pr create --base main --title "fix(mcp): critical bug description"
```

## Version Strategy

`fovux-mcp` and `fovux-studio` use independent semantic-version tracks. The
Python `fovux-mcp` package and npm `fovux-mcp` wrapper are linked because the
wrapper executes the matching Python package version. The MCP package remains the
source for `mcp.json`, `fovux-mcp/server.json`, and `fovux-mcp/smithery.yaml`.
Public tracks start from `1.0.0` in `oaslananka/fovux-kit`; Studio publishes
under `oaslananka.fovuxstudiokit`. The verified first-public release is complete,
so subsequent versions are calculated normally from Conventional Commits.

After registry verification succeeds, the release workflow opens or updates a protected-branch post-release baseline pull request. That PR promotes candidate wording and pending channel statuses to the reviewed published truth; do not edit the published baseline directly on main.
