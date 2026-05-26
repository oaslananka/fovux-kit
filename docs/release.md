# Release Process

Fovux uses a protected release model.

| Repo                   | Role                                  |
| ---------------------- | ------------------------------------- |
| `oaslananka/fovux`     | Public developer-facing repository    |
| `oaslananka-lab/fovux` | CI/CD, security gates, and publishing |

## Release Tracks

### fovux-mcp to PyPI

- Versioned from Conventional Commits through the grouped release-please PR on the org repository.
- Release artifacts are built from the tagged source.
- GitHub Release artifacts, SBOMs, checksums, and provenance are always attached
  first.
- PyPI publishing prefers trusted publishing when
  `PYPI_TRUSTED_PUBLISHING_ENABLED=true` and the PyPI trusted publisher matches
  `oaslananka-lab/fovux`, environment `pypi-production`, and
  `.github/workflows/release-please.yml`.
- Until trusted publishing is configured, the guarded production job may use
  `PYPI_TOKEN` from the `pypi-production` environment. Only wheel and sdist
  files from the GitHub Actions runner are uploaded to PyPI.
- A package release fails closed when neither trusted publishing nor `PYPI_TOKEN`
  is available.

### fovux-studio to VS Marketplace and Open VSX

- Versioned from the same grouped release-please PR as `fovux-mcp`.
- The release workflow packages the extension with the VS Code extension CLI.
- Marketplace publishing runs only when `VSCE_PAT` and `OVSX_PAT` are configured
  in the `vsce-production` environment or org repo secrets.

## Normal Release

1. Merge changes to `main` through a reviewed pull request.
2. CI, CodeQL, security scans, and review gates pass on the org repository.
3. release-please opens one grouped release PR with version and changelog updates.
4. A maintainer reviews and merges the release PR.
5. Publish jobs run for each package that received a release.
6. SBOM, SHA256 checksum, and provenance assets are attached to the GitHub Release.

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

Both packages use linked semantic versioning. The release-please `linked-versions`
plugin keeps `fovux-mcp`, `fovux-studio`, `mcp.json`, `fovux-mcp/server.json`,
and `fovux-mcp/smithery.yaml` on the same release version.
