#!/usr/bin/env bash
set -euo pipefail

# Verify Sigstore signatures for release artifacts.
# Usage: bash scripts/verify_signatures.sh dist/

DIST_DIR="${1:?Usage: verify_signatures.sh <dist-dir>}"

if ! command -v sigstore &>/dev/null; then
  echo "sigstore CLI not found. Install with: uv tool install sigstore"
  exit 1
fi

echo "=== Verifying Sigstore signatures ==="
echo "Directory: $DIST_DIR"

found=0
for artifact in "$DIST_DIR"/*.whl "$DIST_DIR"/*.tar.gz; do
  [ -f "$artifact" ] || continue
  found=$((found + 1))
  echo ""
  echo "Verifying: $(basename "$artifact")"
  sigstore verify identity \
    --cert-identity "https://github.com/oaslananka-lab/fovux/.github/workflows/release-please.yml@refs/heads/main" \
    --cert-oidc-issuer "https://token.actions.githubusercontent.com" \
    "$artifact" || {
    echo "FAILED: $artifact"
    exit 1
  }
  echo "OK: $(basename "$artifact")"
done

if [ "$found" -eq 0 ]; then
  echo "No artifacts found in $DIST_DIR"
  exit 1
fi

echo ""
echo "=== All $found artifacts verified ==="
