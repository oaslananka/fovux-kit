"""Tests for shared dataset utility guardrails."""

from __future__ import annotations

from pathlib import Path

import pytest

from fovux.core.dataset_utils import find_images


def test_find_images_rejects_filesystem_root_without_scanning() -> None:
    """Filesystem roots are too broad to treat as dataset directories."""
    root = Path(Path.cwd().anchor)

    assert find_images(root) == []


def test_find_images_rejects_root_equivalent_path_without_scanning() -> None:
    """Root-equivalent inputs should be rejected after canonicalization."""
    root_equivalent = Path(Path.cwd().anchor) / "definitely-missing" / ".."

    assert find_images(root_equivalent) == []


def test_find_images_canonicalizes_current_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Relative dataset paths should resolve before the root guard runs."""
    (tmp_path / "image.jpg").write_bytes(b"not-real-image")
    monkeypatch.chdir(tmp_path)

    assert [path.name for path in find_images(Path("."))] == ["image.jpg"]


def test_find_images_returns_sorted_images(tmp_path: Path) -> None:
    """Normal dataset directories should still return supported image files."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    (images_dir / "b.png").write_bytes(b"not-real-image")
    (images_dir / "a.jpg").write_bytes(b"not-real-image")
    (images_dir / "notes.txt").write_text("skip", encoding="utf-8")

    assert [path.name for path in find_images(tmp_path)] == ["a.jpg", "b.png"]
