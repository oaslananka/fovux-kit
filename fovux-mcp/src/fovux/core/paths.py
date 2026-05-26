"""Fovux home directory resolution and path helpers."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path


def get_fovux_home() -> Path:
    """Resolve the Fovux home directory.

    Priority order:
    1. FOVUX_HOME environment variable
    2. ~/.fovux

    Returns:
        Absolute Path to the Fovux home directory.
    """
    env_home = os.environ.get("FOVUX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()

    default_home = Path.home() / ".fovux"
    return default_home


def ensure_fovux_dirs(home: Path | None = None) -> FovuxPaths:
    """Create all required Fovux subdirectories and return a FovuxPaths instance.

    Args:
        home: Override the home directory (defaults to get_fovux_home()).

    Returns:
        FovuxPaths with all directories created.
    """
    if home is None:
        home = get_fovux_home()
    paths = FovuxPaths(home)
    paths.runs.mkdir(parents=True, exist_ok=True)
    paths.models.mkdir(parents=True, exist_ok=True)
    paths.cache.mkdir(parents=True, exist_ok=True)
    paths.exports.mkdir(parents=True, exist_ok=True)
    paths.datasets.mkdir(parents=True, exist_ok=True)
    return paths


class FovuxPaths:
    """Typed container for all Fovux filesystem paths.

    Attributes:
        home: Root Fovux data directory.
        runs: Training run directories.
        models: Pretrained / imported checkpoints.
        cache: Perceptual hashes, thumbnails, dataset cache.
        exports: Exported ONNX / TFLite / TensorRT artifacts.
        datasets: Indexed dataset metadata (not raw images).
        runs_db: SQLite runs index.
        config_file: User-level config.toml.
    """

    def __init__(
        self,
        home: Path,
        path_overrides: Mapping[str, str] | None = None,
        *,
        load_config_file: bool = True,
    ) -> None:
        """Initialize with a home directory."""
        self.home = home.expanduser().resolve()
        self.config_file = self.home / "config.toml"
        overrides = dict(path_overrides or {})
        if path_overrides is None and load_config_file:
            overrides.update(_load_path_overrides(self.config_file))
        self.runs = _resolve_child_path(self.home, overrides.get("runs", "runs"))
        self.models = _resolve_child_path(self.home, overrides.get("models", "models"))
        self.cache = _resolve_child_path(self.home, overrides.get("cache", "cache"))
        self.exports = _resolve_child_path(self.home, overrides.get("exports", "exports"))
        self.datasets = self.home / "datasets"
        self.runs_db = self.home / "runs.db"

    def run_dir(self, run_id: str) -> Path:
        """Return the directory for a specific run.

        Args:
            run_id: The run identifier string.

        Returns:
            Path to the run directory.
        """
        return self.runs / run_id

    def __repr__(self) -> str:
        """Return debug representation."""
        return f"FovuxPaths(home={self.home})"


def _resolve_child_path(home: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (home / path).resolve()


def _load_path_overrides(config_file: Path) -> dict[str, str]:
    if not config_file.exists():
        return {}
    try:
        with config_file.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    fovux = raw.get("fovux")
    if not isinstance(fovux, dict):
        return {}
    paths = fovux.get("paths")
    if not isinstance(paths, dict):
        return {}
    return {
        key: value
        for key, value in paths.items()
        if key in {"runs", "models", "cache", "exports"} and isinstance(value, str)
    }
