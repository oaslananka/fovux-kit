#!/usr/bin/env bash
# Nightly: test fovux-mcp against latest allowed dependency versions.
set -euo pipefail

REPORT_FILE="${BASH_SOURCE%/*}/../nightly-compat-report.txt"
echo "Nightly Compatibility Report - $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$REPORT_FILE"
echo "Commit: ${GITHUB_SHA:-local}" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "=== Installing latest compatible deps ===" | tee -a "$REPORT_FILE"
# Test latest permitted packages without making the repository lockfile
# assertions read the temporary upgraded dependency resolution.
LOCK_FILE="${BASH_SOURCE%/*}/../uv.lock"
SAVED_LOCK="$(mktemp)"
cp "$LOCK_FILE" "$SAVED_LOCK"
restore_lock() {
  cp "$SAVED_LOCK" "$LOCK_FILE"
  rm -f "$SAVED_LOCK"
}
trap restore_lock EXIT
uv sync --upgrade --extra dev --no-build 2>&1 | tee -a "$REPORT_FILE"
restore_lock
trap - EXIT

echo "=== Running test suite ===" | tee -a "$REPORT_FILE"
uv run --no-sync pytest -x -q -m "not slow and not gpu and not network" --tb=short 2>&1 | tee -a "$REPORT_FILE"

echo "=== Compat check passed ===" | tee -a "$REPORT_FILE"
