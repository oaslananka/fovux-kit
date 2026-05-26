"""Dependency boundary tests for optional backend integrations."""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

from tests.path_helpers import find_package_root


def test_core_import_does_not_import_ultralytics() -> None:
    """Importing Fovux core modules should not load the optional YOLO backend."""
    project_root = find_package_root(Path(__file__))
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            [str(project_root / "src"), os.environ.get("PYTHONPATH", "")]
        ),
    }
    script = (
        "import importlib, sys;"
        "importlib.import_module('fovux');"
        "importlib.import_module('fovux.core.auth');"
        "raise SystemExit(1 if 'ultralytics' in sys.modules else 0)"
    )
    result = subprocess.run(  # noqa: S603 - fixed interpreter and constant import probe.
        [sys.executable, "-c", script],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_ultralytics_is_declared_as_optional_extra() -> None:
    """The package metadata should keep AGPL/commercial-boundary deps optional."""
    pyproject = find_package_root(Path(__file__)) / "pyproject.toml"
    payload = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    dependencies = payload["project"]["dependencies"]
    optional = payload["project"]["optional-dependencies"]

    assert all(not str(dep).startswith("ultralytics") for dep in dependencies)
    assert any(str(dep).startswith("ultralytics") for dep in optional["yolo"])
