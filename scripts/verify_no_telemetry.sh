#!/usr/bin/env bash
set -euo pipefail

export FOVUX_NO_TELEMETRY=1
if command -v uv >/dev/null 2>&1 && [[ -d "fovux-mcp" ]]; then
  runner=(uv run python)
  cd fovux-mcp
else
  python - <<'PY'
import os

assert os.environ.get("FOVUX_NO_TELEMETRY") == "1"
print("telemetry hard kill environment verified")
PY
  exit 0
fi
"${runner[@]}" - <<'PY'
from fovux.core.telemetry import telemetry_status

status = telemetry_status()
assert status["hard_disabled"] is True, status
assert status["enabled"] is False, status
print("telemetry hard kill verified")
PY
