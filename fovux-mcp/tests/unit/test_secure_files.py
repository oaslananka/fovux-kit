"""Unit tests for symlink-safe atomic file writes."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from fovux.core.errors import FovuxPathValidationError
from fovux.core.secure_files import atomic_write_text, resolve_under_root


def test_resolve_under_root_accepts_normal_relative_path(tmp_path: Path) -> None:
    """Normal nested relative paths should resolve below the trusted root."""
    assert (
        resolve_under_root(tmp_path, Path("nested/file.json"))
        == (tmp_path / "nested" / "file.json").resolve()
    )


@pytest.mark.parametrize("relative", [Path("../escape"), Path("nested/../../escape")])
def test_resolve_under_root_rejects_parent_traversal(tmp_path: Path, relative: Path) -> None:
    """Lexical parent traversal must be rejected before filesystem access."""
    with pytest.raises(FovuxPathValidationError, match="relative path"):
        resolve_under_root(tmp_path, relative)


def test_resolve_under_root_rejects_absolute_path(tmp_path: Path) -> None:
    """Callers must supply a relative path rather than replacing the trust root."""
    with pytest.raises(FovuxPathValidationError, match="relative path"):
        resolve_under_root(tmp_path, (tmp_path / "absolute.json").resolve())


def test_resolve_under_root_rejects_final_symlink(tmp_path: Path) -> None:
    """A sensitive target may not itself be a symlink."""
    outside = tmp_path.parent / f"{tmp_path.name}-outside.json"
    outside.write_text("sentinel", encoding="utf-8")
    (tmp_path / "linked.json").symlink_to(outside)
    try:
        with pytest.raises(FovuxPathValidationError, match="symlink"):
            resolve_under_root(tmp_path, Path("linked.json"))
    finally:
        outside.unlink(missing_ok=True)


def test_resolve_under_root_rejects_parent_symlink_escape(tmp_path: Path) -> None:
    """A parent-directory symlink must not redirect a nested write outside the root."""
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(FovuxPathValidationError, match="escapes"):
            resolve_under_root(tmp_path, Path("linked/file.json"))
    finally:
        outside.rmdir()


def test_atomic_write_text_replaces_file_with_requested_mode(tmp_path: Path) -> None:
    """Atomic replacement should persist complete content with private permissions."""
    target = atomic_write_text(tmp_path, Path("state.json"), "first", mode=0o600)
    replaced = atomic_write_text(tmp_path, Path("state.json"), "second", mode=0o600)

    assert replaced == target
    assert target.read_text(encoding="utf-8") == "second"
    if sys.platform != "win32":
        assert target.stat().st_mode & 0o777 == 0o600


def test_atomic_write_text_cleans_temporary_file_when_replace_fails(tmp_path: Path) -> None:
    """A failed atomic replace must not leave secret-bearing temp files behind."""
    with (
        patch("fovux.core.secure_files.os.replace", side_effect=OSError("blocked")),
        pytest.raises(OSError, match="blocked"),
    ):
        atomic_write_text(tmp_path, Path("state.json"), "secret")

    assert list(tmp_path.glob(".state.json.*.tmp")) == []
    assert not (tmp_path / "state.json").exists()
