"""Local-first telemetry configuration helpers.

Telemetry is disabled by default and never sends data unless explicitly enabled.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

import tomli_w

from fovux.config import clear_config_cache, load_config
from fovux.core.paths import get_fovux_home


def telemetry_status() -> dict[str, object]:
    """Return effective telemetry status without sending network traffic."""
    config = load_config()
    return {
        "enabled": config.telemetry_enabled,
        "configured_enabled": config.telemetry.enabled,
        "endpoint": config.telemetry.endpoint,
        "hard_disabled": bool(os.environ.get("FOVUX_NO_TELEMETRY", "").strip()),
    }


def set_telemetry(*, enabled: bool, endpoint: str | None = None) -> dict[str, object]:
    """Persist telemetry configuration under FOVUX_HOME/config.toml."""
    config_path = get_fovux_home() / "config.toml"
    raw = _read_config(config_path)
    fovux = raw.setdefault("fovux", {})
    if not isinstance(fovux, dict):
        fovux = {}
        raw["fovux"] = fovux
    telemetry = fovux.setdefault("telemetry", {})
    if not isinstance(telemetry, dict):
        telemetry = {}
        fovux["telemetry"] = telemetry
    telemetry["enabled"] = enabled
    if endpoint is not None:
        telemetry["endpoint"] = endpoint

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("wb") as handle:
        tomli_w.dump(raw, handle)
    clear_config_cache()
    return telemetry_status()


def _read_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    with config_path.open("rb") as handle:
        return dict(tomllib.load(handle))
