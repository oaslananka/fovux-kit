"""Tests for local-first telemetry helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from fovux.config import clear_config_cache
from fovux.core.telemetry import set_telemetry, telemetry_status


def test_set_telemetry_persists_config(
    tmp_fovux_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Telemetry opt-in should be persisted under FOVUX_HOME/config.toml."""
    monkeypatch.delenv("FOVUX_NO_TELEMETRY", raising=False)

    status = set_telemetry(enabled=True, endpoint="https://telemetry.example.test/events")

    assert status["enabled"] is True
    assert status["configured_enabled"] is True
    assert status["endpoint"] == "https://telemetry.example.test/events"
    assert (tmp_fovux_home / "config.toml").exists()


def test_telemetry_hard_disable_overrides_config(
    tmp_fovux_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FOVUX_NO_TELEMETRY should disable telemetry without rewriting config."""
    set_telemetry(enabled=True, endpoint="https://telemetry.example.test/events")
    monkeypatch.setenv("FOVUX_NO_TELEMETRY", "1")
    clear_config_cache()

    status = telemetry_status()

    assert status["enabled"] is False
    assert status["configured_enabled"] is True
    assert status["hard_disabled"] is True
    assert tmp_fovux_home.joinpath("config.toml").read_text(encoding="utf-8")


def test_set_telemetry_recovers_from_non_table_values(tmp_fovux_home: Path) -> None:
    """Existing malformed fovux/telemetry values should be replaced safely."""
    config_path = tmp_fovux_home / "config.toml"
    config_path.write_text('[fovux]\ntelemetry = "bad"\n', encoding="utf-8")
    clear_config_cache()

    status = set_telemetry(enabled=False, endpoint="https://telemetry.example.test/events")

    assert status["enabled"] is False
    assert status["endpoint"] == "https://telemetry.example.test/events"
