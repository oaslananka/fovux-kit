# Release Process

Releases are automated from merges to `main` in `oaslananka/fovux-kit`.

1. A maintainer merges a normal pull request with Conventional Commits.
2. `release-please` evaluates commit history and updates package version files plus package changelogs in one grouped release pull request.
3. A maintainer reviews and merges the release pull request.
4. The release workflow creates the GitHub Release from release-please outputs.
5. Publish jobs build artifacts on GitHub-hosted runners, generate SBOMs and SHA256 checksums, attest provenance, attach assets, publish to registries, and verify the release.

Version numbers are normally never supplied manually. The current first-public
release uses a temporary release-please `release-as: 1.0.0` override to keep all
public artifacts at the required registry baseline; remove that override after
the first verified publish. The Python `fovux-mcp` package and npm wrapper are
linked; `fovux-studio` remains an independent release track. Release tags remain
component-specific for the monorepo packages.
