#!/usr/bin/env bash
# Nightly: test fovux-mcp against latest allowed dependency versions.
set -euo pipefail

SCRIPT_DIR="${BASH_SOURCE%/*}"
PROJECT_DIR="${SCRIPT_DIR}/.."
REPORT_FILE="${PROJECT_DIR}/nightly-compat-report.txt"
LOCKFILE="${PROJECT_DIR}/uv.lock"
LOCKFILE_BACKUP="${LOCKFILE}.bak"

echo "Nightly Compatibility Report - $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$REPORT_FILE"
echo "Commit: ${GITHUB_SHA:-local}" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

cleanup() {
    if [[ -f "$LOCKFILE_BACKUP" ]]; then
        mv "$LOCKFILE_BACKUP" "$LOCKFILE"
    fi
}
trap cleanup EXIT

echo "=== Installing latest compatible deps ===" | tee -a "$REPORT_FILE"
cp "$LOCKFILE" "$LOCKFILE_BACKUP"
uv sync --upgrade --extra dev 2>&1 | tee -a "$REPORT_FILE"

echo "=== Running test suite ===" | tee -a "$REPORT_FILE"
uv run --no-sync pytest -x -q -m "not slow and not gpu and not network" --tb=short 2>&1 | tee -a "$REPORT_FILE"

echo "=== Compat check passed ===" | tee -a "$REPORT_FILE"
