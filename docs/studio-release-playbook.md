# Fovux Studio Release Evidence and Rollback Playbook

## Required release evidence

Each Studio release must produce:

- Built VSIX artifact.
- VSIX SHA256 checksum.
- Studio SBOM.
- GitHub provenance attestation where supported.
- Registry verification report for VS Marketplace and Open VSX publication.
- Package-size gate evidence from `scripts/package_vscode_extension.mjs --max-size-bytes`.

## Package-size gate

The production workflow packages the extension through `scripts/package_vscode_extension.mjs` and fails when
the VSIX exceeds the configured byte budget. `.vscodeignore` is part of the packaging contract and must keep
source, tests, maps, temp files, and local credentials out of the artifact.

## Rollback playbook

1. Identify the bad release tag, VSIX SHA256, Marketplace version, and Open VSX version.
2. Stop further release jobs and open an incident issue.
3. Publish a fixed patch release whenever possible; prefer deprecation over deletion.
4. If required, unpublish or yank the affected Marketplace/Open VSX version using registry owner controls.
5. Attach registry verification evidence and release notes explaining the rollback.
6. Re-run registry verification before closing the incident.
