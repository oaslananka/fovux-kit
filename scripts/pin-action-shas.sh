#!/usr/bin/env bash
set -euo pipefail

echo "=== Checking GitHub Actions SHA pinning ==="

workflows_dir=".github/workflows"
if [ ! -d "$workflows_dir" ]; then
  echo "No workflow directory found."
  exit 0
fi

if grep -R "^[[:space:]]*uses:" "$workflows_dir" | grep -v "@[0-9a-f]\{40\}"; then
  echo ""
  echo "ERROR: Unpinned actions found. Pin every external action to a full commit SHA."
  exit 1
fi

echo "All actions are SHA-pinned."
