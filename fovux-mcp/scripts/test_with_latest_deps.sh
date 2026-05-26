#!/usr/bin/env bash
# Nightly: test fovux-mcp against latest allowed dependency versions.
set -euo pipefail

REPORT_FILE="${BASH_SOURCE%/*}/../nightly-compat-report.txt"
echo "Nightly Compatibility Report - $(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$REPORT_FILE"
echo "Commit: ${GITHUB_SHA:-local}" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "=== Installing latest compatible deps ===" | tee -a "$REPORT_FILE"
uv sync --upgrade --extra dev 2>&1 | tee -a "$REPORT_FILE"

echo "=== Running test suite ===" | tee -a "$REPORT_FILE"
uv run pytest -x -q -m "not slow and not gpu and not network" --tb=short 2>&1 | tee -a "$REPORT_FILE"

echo "=== Compat check passed ===" | tee -a "$REPORT_FILE"
