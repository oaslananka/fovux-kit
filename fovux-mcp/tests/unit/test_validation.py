"""Tests for local filesystem validation helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from fovux.config import write_default_config
from fovux.core.errors import FovuxPathValidationError
from fovux.core.validation import (
    ensure_within_root,
    max_file_size_bytes,
    resolve_local_path,
    validate_file_size,
)


def test_resolve_local_path_expands_and_resolves(tmp_path: Path) -> None:
    """resolve_local_path should return the resolved absolute path."""
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello")
    assert resolve_local_path(file_path) == file_path.resolve()


def test_ensure_within_root_accepts_in_root(tmp_path: Path) -> None:
    """A child path inside the root should be accepted."""
    root = tmp_path / "root"
    child = root / "nested" / "file.txt"
    child.parent.mkdir(parents=True)
    child.write_text("ok")

    assert ensure_within_root(child, root) == child.resolve()


def test_ensure_within_root_rejects_parent_traversal(tmp_path: Path) -> None:
    """A resolved path outside the root should be rejected."""
    root = tmp_path / "root"
    root.mkdir()
    outside = root / ".." / "outside.txt"

    with pytest.raises(FovuxPathValidationError):
        ensure_within_root(outside, root)


def test_ensure_within_root_rejects_symlink_escape(tmp_path: Path) -> None:
    """Symlinks escaping the root should be rejected when supported."""
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("escape")
    link = root / "escape.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("Symlinks are not available in this environment.")

    with pytest.raises(FovuxPathValidationError):
        ensure_within_root(link, root)


def test_validate_file_size_rejects_large_files(tmp_path: Path) -> None:
    """validate_file_size should reject files over the provided limit."""
    file_path = tmp_path / "large.bin"
    file_path.write_bytes(b"0123456789")

    with pytest.raises(FovuxPathValidationError):
        validate_file_size(file_path, max_bytes=4)


def test_max_file_size_bytes_reads_config(tmp_fovux_home: Path) -> None:
    """Configured validation limits should flow through max_file_size_bytes."""
    config_path = tmp_fovux_home / "config.toml"
    write_default_config(config_path)
    content = config_path.read_text().replace("max_file_size_mb = 100", "max_file_size_mb = 7")
    config_path.write_text(content)

    assert max_file_size_bytes() == 7 * 1024 * 1024
