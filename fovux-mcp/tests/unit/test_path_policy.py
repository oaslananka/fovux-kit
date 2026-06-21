"""Unit tests for the centralized path policy layer."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from fovux.core.errors import FovuxPathValidationError
from fovux.core.path_policy import (
    check_path_policy,
    get_fovux_temp_dir,
    reset_active_tool,
    set_active_tool,
)
from fovux.core.paths import get_fovux_home


def test_fovux_temp_dir() -> None:
    """The temp dir must be a Fovux-specific subdirectory under system temp."""
    temp_dir = get_fovux_temp_dir()
    assert temp_dir.name == "fovux"
    assert temp_dir.exists()


def test_windows_reserved_names(tmp_path: Path) -> None:
    """Paths containing reserved device names must be rejected."""
    bad_path = tmp_path / "CON.txt"
    with pytest.raises(FovuxPathValidationError, match="uses reserved Windows device name"):
        check_path_policy(bad_path)

    bad_folder = tmp_path / "LPT3" / "file.json"
    with pytest.raises(FovuxPathValidationError, match="uses reserved Windows device name"):
        check_path_policy(bad_folder)


def test_path_policy_enforcement_by_tool_category(tmp_path: Path) -> None:
    """Path checks should respect the active tool category and its write status."""
    # Simulating read_only tool
    a1, r1 = set_active_tool("dataset_inspect", {"dataset_path": tmp_path})
    try:
        # Read should be allowed
        check_path_policy(tmp_path, write=False)

        # Write must fail under read_only tool policy
        with pytest.raises(FovuxPathValidationError, match="Write operation is prohibited"):
            check_path_policy(tmp_path, write=True)
    finally:
        reset_active_tool(a1, r1)

    # Simulating export_write tool
    a2, r2 = set_active_tool("export_onnx", {"checkpoint": tmp_path})
    try:
        # Allowed write target (exports dir)
        exports_dir = get_fovux_home() / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        check_path_policy(exports_dir / "model.onnx", write=True)

        # Disallowed write target (e.g. random root)
        outside_path = Path("/etc/passwd" if sys.platform != "win32" else "C:/Windows/System32")
        with pytest.raises(FovuxPathValidationError, match="escapes allowed roots"):
            check_path_policy(outside_path, write=True)
    finally:
        reset_active_tool(a2, r2)


def test_symlink_traversal_prevention(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Symlinks escaping allowed roots must be caught and rejected."""
    monkeypatch.setenv("FOVUX_TEST_ALLOW_TEMP_DIR", "0")
    # Skip symlink tests if OS doesn't support them or lacks permissions (like on Windows non-admin)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    inside_dir = tmp_path / "inside"
    inside_dir.mkdir()

    symlink_path = inside_dir / "escaped_link"
    try:
        symlink_path.symlink_to(outside_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are not supported or permitted in this environment")

    # Set policy allowed roots only to inside_dir
    a, r = set_active_tool("dataset_augment", {"dataset_path": inside_dir})
    try:
        # Read the symlink pointing outside allowed root inside_dir
        with pytest.raises(FovuxPathValidationError, match="escapes allowed roots"):
            check_path_policy(symlink_path / "some_file.png", write=False)
    finally:
        reset_active_tool(a, r)
