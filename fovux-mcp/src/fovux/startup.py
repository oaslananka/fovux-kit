"""Opt-in startup timing diagnostics for the stdio MCP process."""

from __future__ import annotations

import json
import os
import sys
import time

_PROCESS_STARTED_AT = time.perf_counter()
_DIAGNOSTICS_ENV = "FOVUX_STARTUP_DIAGNOSTICS"


def startup_checkpoint(stage: str, **details: object) -> None:
    """Write one bounded structured timing record to stderr when explicitly enabled."""
    if os.environ.get(_DIAGNOSTICS_ENV, "").strip().lower() not in {"1", "true", "yes"}:
        return
    record = {
        "event": "fovux_startup",
        "stage": stage,
        "elapsed_ms": round((time.perf_counter() - _PROCESS_STARTED_AT) * 1000, 3),
        **details,
    }
    sys.stderr.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    sys.stderr.flush()
