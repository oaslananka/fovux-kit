"""Fovux configuration loader.

Reads config.toml from FOVUX_HOME, applies environment variable overrides,
and exposes a typed FovuxConfig object.
"""

from __future__ import annotations

import os
import time
import tomllib
from pathlib import Path
from typing import Any

import tomli_w
from pydantic import BaseModel, Field

from fovux.core.paths import FovuxPaths, get_fovux_home

_CONFIG_CACHE_TTL_SECONDS = 30.0
_CONFIG_CACHE: dict[str, tuple[FovuxConfig, float, float]] = {}


class PathsConfig(BaseModel):
    """Filesystem path configuration."""

    home: str = "~/.fovux"
    runs: str = "runs"
    models: str = "models"
    cache: str = "cache"
    exports: str = "exports"


class TrainingConfig(BaseModel):
    """Default training parameters."""

    default_device: str = "auto"
    default_workers: int = 8
    default_patience: int = 50


class InferenceConfig(BaseModel):
    """Default inference parameters."""

    default_conf: float = 0.25
    default_iou: float = 0.45


class UIConfig(BaseModel):
    """UI preferences."""

    preferred_backend: str = "onnxruntime"


class TelemetryConfig(BaseModel):
    """Telemetry configuration. Off by default."""

    enabled: bool = False
    endpoint: str = ""


class ValidationConfig(BaseModel):
    """Filesystem safety limits for local processing."""

    max_file_size_mb: int = 100


class FovuxConfig(BaseModel):
    """Root Fovux configuration."""

    version: str = "1.0"
    paths: PathsConfig = Field(default_factory=PathsConfig)
    training: TrainingConfig = Field(default_factory=TrainingConfig)
    inference: InferenceConfig = Field(default_factory=InferenceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)

    @property
    def fovux_paths(self) -> FovuxPaths:
        """Return a FovuxPaths resolved from the current config."""
        env_home = os.environ.get("FOVUX_HOME")
        home = Path(env_home).expanduser().resolve() if env_home else Path(self.paths.home)
        return FovuxPaths(home, self.paths.model_dump(), load_config_file=False)

    @property
    def telemetry_enabled(self) -> bool:
        """Return effective telemetry setting, respecting FOVUX_NO_TELEMETRY."""
        if os.environ.get("FOVUX_NO_TELEMETRY", "").strip():
            return False
        return self.telemetry.enabled


def load_config(config_path: Path | None = None) -> FovuxConfig:
    """Load Fovux configuration from config.toml.

    Priority: env vars > config.toml > defaults.

    Args:
        config_path: Override path to config.toml. Defaults to FOVUX_HOME/config.toml.

    Returns:
        Validated FovuxConfig instance.
    """
    target_path = config_path or (get_fovux_home() / "config.toml")
    return _load_config_cached(str(target_path))


def _load_config_cached(config_path: str) -> FovuxConfig:
    now = time.monotonic()
    raw: dict[str, Any] = {}
    path = Path(config_path)
    current_mtime = _safe_mtime(path)
    cached = _CONFIG_CACHE.get(config_path)
    if cached is not None:
        cached_config, cached_at, cached_mtime = cached
        if now - cached_at < _CONFIG_CACHE_TTL_SECONDS and current_mtime == cached_mtime:
            return cached_config

    if path.exists():
        with path.open("rb") as f:
            raw = tomllib.load(f)

    config = FovuxConfig.model_validate(raw.get("fovux", {}))
    _CONFIG_CACHE[config_path] = (config, now, current_mtime)

    return config


def clear_config_cache() -> None:
    """Clear the process-local configuration cache."""
    _CONFIG_CACHE.clear()


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime if path.exists() else 0.0
    except OSError:
        return 0.0


def write_default_config(config_path: Path) -> None:
    """Write a default config.toml to the given path.

    Args:
        config_path: Destination path for config.toml.
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
    default: dict[str, Any] = {
        "fovux": {
            "version": "1.0",
            "paths": {
                "home": "~/.fovux",
                "runs": "runs",
                "models": "models",
                "cache": "cache",
                "exports": "exports",
            },
            "training": {
                "default_device": "auto",
                "default_workers": 8,
                "default_patience": 50,
            },
            "inference": {
                "default_conf": 0.25,
                "default_iou": 0.45,
            },
            "ui": {
                "preferred_backend": "onnxruntime",
            },
            "telemetry": {
                "enabled": False,
                "endpoint": "",
            },
            "validation": {
                "max_file_size_mb": 100,
            },
        }
    }
    with config_path.open("wb") as f:
        tomli_w.dump(default, f)
