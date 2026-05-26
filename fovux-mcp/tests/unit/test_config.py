"""Unit tests for fovux.config."""

from __future__ import annotations

from pathlib import Path

import pytest

import fovux.config as config_module
from fovux.config import FovuxConfig, clear_config_cache, load_config, write_default_config


def test_default_config_values() -> None:
    """FovuxConfig should have sane defaults."""
    cfg = FovuxConfig()
    assert cfg.version == "1.0"
    assert cfg.training.default_device == "auto"
    assert cfg.training.default_workers == 8
    assert cfg.inference.default_conf == 0.25
    assert cfg.telemetry.enabled is False


def test_load_config_nonexistent_file(tmp_path: Path) -> None:
    """load_config with a nonexistent file should return defaults."""
    cfg = load_config(config_path=tmp_path / "no_such.toml")
    assert isinstance(cfg, FovuxConfig)
    assert cfg.version == "1.0"


def test_write_and_reload_config(tmp_path: Path) -> None:
    """write_default_config + load_config should round-trip."""
    config_path = tmp_path / "config.toml"
    write_default_config(config_path)
    assert config_path.exists()
    cfg = load_config(config_path=config_path)
    assert cfg.version == "1.0"
    assert cfg.training.default_patience == 50


def test_telemetry_disabled_by_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FOVUX_NO_TELEMETRY env var should disable telemetry regardless of config."""
    monkeypatch.setenv("FOVUX_NO_TELEMETRY", "1")
    cfg = FovuxConfig(telemetry={"enabled": True})  # type: ignore[arg-type]
    assert cfg.telemetry_enabled is False


def test_validation_config_defaults() -> None:
    """Validation config should default to a 100 MB safety limit."""
    cfg = FovuxConfig()
    assert cfg.validation.max_file_size_mb == 100


def test_fovux_paths_respects_paths_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """FovuxPaths should consume configured subdirectory overrides."""
    monkeypatch.setenv("FOVUX_HOME", str(tmp_path / "home"))
    cfg = FovuxConfig(
        paths={
            "runs": "training-runs",
            "models": "model-library",
            "cache": "cache-store",
            "exports": "exported-artifacts",
        }
    )

    paths = cfg.fovux_paths

    assert paths.home == tmp_path / "home"
    assert paths.runs == paths.home / "training-runs"
    assert paths.models == paths.home / "model-library"
    assert paths.cache == paths.home / "cache-store"
    assert paths.exports == paths.home / "exported-artifacts"
    assert paths.datasets == paths.home / "datasets"


def test_clear_config_cache_reflects_file_changes(tmp_path: Path) -> None:
    """Clearing the cache should make the next load read the updated file contents."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("[fovux.training]\ndefault_workers = 4\n", encoding="utf-8")
    first = load_config(config_path=config_path)
    assert first.training.default_workers == 4

    config_path.write_text("[fovux.training]\ndefault_workers = 16\n", encoding="utf-8")
    clear_config_cache()
    second = load_config(config_path=config_path)

    assert second.training.default_workers == 16


def test_config_cache_ttl_can_force_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Expired cache entries should reload updated config data from disk."""
    config_path = tmp_path / "config.toml"
    config_path.write_text("[fovux.training]\ndefault_workers = 2\n", encoding="utf-8")
    clear_config_cache()
    load_config(config_path=config_path)

    config_path.write_text("[fovux.training]\ndefault_workers = 12\n", encoding="utf-8")
    monkeypatch.setattr(config_module, "_CONFIG_CACHE_TTL_SECONDS", 0.0)
    reloaded = load_config(config_path=config_path)

    assert reloaded.training.default_workers == 12
