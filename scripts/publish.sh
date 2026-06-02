#!/usr/bin/env bash
set -euo pipefail

# Publish fovux-mcp (Python)
if [ -d "fovux-mcp" ]; then
  echo "Publishing fovux-mcp to PyPI..."
  uv publish fovux-mcp/dist/*.whl fovux-mcp/dist/*.tar.gz
fi

# Publish fovux-studio (VS Code Marketplace and Open VSX)
if [ -d "fovux-studio" ]; then
  cd fovux-studio
  VSIX_FILE="fovuxstudiokit.vsix"
  EXTENSION_ID="$(node -p "require('./package.json').publisher + '.' + require('./package.json').name")"
  if [ "$EXTENSION_ID" != "oaslananka.fovuxstudiokit" ]; then
    echo "Unexpected Studio extension id: $EXTENSION_ID" >&2
    exit 1
  fi

  if [ -n "${VSCE_PAT:-}" ]; then
    echo "Publishing to VS Code Marketplace..."
    node ../scripts/publish_vscode_extension.mjs marketplace \
      --vsix "$VSIX_FILE" \
      --publisher oaslananka \
      --name fovuxstudiokit \
      --version "$(node -p "require('./package.json').version")"
  fi

  if [ -n "${OVSX_PAT:-}" ]; then
    echo "Publishing to Open VSX..."
    node ../scripts/publish_vscode_extension.mjs open-vsx \
      --vsix "$VSIX_FILE" \
      --publisher oaslananka \
      --name fovuxstudiokit \
      --version "$(node -p "require('./package.json').version")"
  fi

  cd ..
fi
