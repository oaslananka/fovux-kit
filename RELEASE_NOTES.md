# Fovux 4.1.4 Release Notes

Fovux 4.1.4 is a patch release that republishes Fovux Studio with the current Marketplace README
screenshot URLs and keeps the backend version aligned for the monorepo release train.

## Headline Wins

- **Adversarial path handling.** Dataset format auto-detection no longer recursively scans an
  arbitrary filesystem root when a fuzzed input points at `/` or a drive root.
- **Stable CI package setup.** GitHub Actions install pinned `pnpm@10.33.0` through npm instead of
  Corepack activation, avoiding Windows/Node 22 runner hangs.
- **Clean security surface.** Dependabot, Trivy, CodeQL, and code-scanning open alerts were
  rechecked after the patch and are clean on the authoritative repository.
- **Pinned supply chain.** GitHub Actions dependencies are pinned to immutable commit SHAs and the
  runtime Docker base image is pinned by digest.
- **Marketplace screenshot paths.** Studio README screenshots resolve to the tracked
  `fovux-studio/resources/screenshots/` assets on `main`.
- **Canonical run streaming.** `/runs/{id}/stream` is now the preferred SSE metrics endpoint, with
  `/runs/{id}/metrics` kept as a compatibility alias.
- **Studio integration polish.** CodeLens actions, run folder decorations, active-run counters,
  profile quick switching, and a structured Doctor tree make common work visible in VS Code.
- **Webview UX completion.** Dataset Inspector, Training Launcher, Export Wizard, and Annotation
  Editor now cover missing labels, bbox distributions, preset import/export, TensorRT visibility,
  and editable YOLO labels.
- **Release-grade CI.** Node 22 plus pinned Node 24 Studio CI, deterministic pnpm installs, strict
  yamllint/actionlint, SBOM upload, Dependabot auto-merge, and release preflight checks are in place.
- **Security signal cleanup.** The runtime Docker image no longer installs unnecessary Mesa/OpenGL
  packages, Trivy is pinned, and upstream-unfixed Debian CVEs no longer flood code scanning.
- **Coverage uplift.** Backend coverage is enforced at 92% and Studio has focused tests for the new
  host/webview behavior.

## Breaking Changes

None. This is a backward-compatible patch release.

## Upgrade Path

```bash
# Backend
cd fovux-mcp
uv sync --locked --extra dev
uv run pytest --no-header -q

# Studio
cd ../fovux-studio
pnpm install --frozen-lockfile
pnpm verify
```

## Release Validation

- `python scripts/check_versions.py` confirms all version sources are coherent.
- `python scripts/quality_gate.py repo-verify` runs the full local validation.
- Backend coverage gate: 92%. Studio coverage gate: 90%.
- `mkdocs build --strict` confirms all 37 tool pages are present and valid.
- VSIX bundle-size checks enforce `out/extension.js <= 500 KB`, each webview bundle <= 1 MB, and
  the packaged VSIX <= 10 MB.

## Previous Release Notes

- [4.1.3](docs/release-notes/4.1.3.md)
- [4.1.2](docs/release-notes/4.1.2.md)
- [4.1.1](docs/release-notes/4.1.1.md)
- [4.1.0](docs/release-notes/4.1.0.md)
- [3.0.0](docs/release-notes/3.0.0.md)
- [2.0.0](docs/release-notes/2.0.0.md)
