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
    pnpm dlx @vscode/vsce@3.9.1 publish --packagePath "$VSIX_FILE" --pat "$VSCE_PAT"
  fi

  if [ -n "${OVSX_PAT:-}" ]; then
    echo "Publishing to Open VSX..."
    pnpm dlx ovsx@0.10.12 publish "$VSIX_FILE" --pat "$OVSX_PAT"
  fi

  cd ..
fi
