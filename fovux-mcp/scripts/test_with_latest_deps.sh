#!/usr/bin/env bash
# Nightly: test fovux-mcp against latest allowed dependency versions.
set -euo pipefail

REPORT_FILE="${BASH_SOURCE%/*}/../nightly-compat-report.txt"
LOCKFILE="${BASH_SOURCE%/*}/../uv.lock"
BACKUP_LOCKFILE="${LOCKFILE}.bak"

echo "Nightly Compatibility Report - $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$REPORT_FILE"
echo "Commit: ${GITHUB_SHA:-local}" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "=== Backing up original lockfile ===" | tee -a "$REPORT_FILE"
cp "$LOCKFILE" "$BACKUP_LOCKFILE"

echo "=== Installing latest compatible deps ===" | tee -a "$REPORT_FILE"
uv sync --upgrade --extra dev 2>&1 | tee -a "$REPORT_FILE"

echo "=== Running test suite with upgraded deps (no-sync) ===" | tee -a "$REPORT_FILE"
uv run --no-sync pytest -x -q -m "not slow and not gpu and not network" --tb=short 2>&1 | tee -a "$REPORT_FILE"

echo "=== Restoring original lockfile ===" | tee -a "$REPORT_FILE"
mv "$BACKUP_LOCKFILE" "$LOCKFILE"

echo "=== Compat check passed ===" | tee -a "$REPORT_FILE"
