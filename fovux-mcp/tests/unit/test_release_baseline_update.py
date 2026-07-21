"""Tests for deterministic post-release baseline synchronization."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = REPO_ROOT / "scripts"
SCRIPT_PATH = SCRIPTS / "update_release_baseline.py"


def _load_module() -> ModuleType:
    assert SCRIPT_PATH.exists(), "release baseline updater is missing"
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("update_release_baseline", SCRIPT_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


def _copy_release_truth_fixture(tmp_path: Path) -> None:
    for relative in (
        "release-baseline.json",
        "ROADMAP.md",
        "RELEASE_NOTES.md",
        "README.md",
    ):
        shutil.copyfile(REPO_ROOT / relative, tmp_path / relative)
    mcp_dir = tmp_path / "fovux-mcp"
    mcp_dir.mkdir()
    shutil.copyfile(REPO_ROOT / "fovux-mcp" / "README.md", mcp_dir / "README.md")
    release_dir = tmp_path / "docs" / "release-notes"
    release_dir.mkdir(parents=True)
    shutil.copyfile(
        REPO_ROOT / "docs" / "release-notes" / "1.5.0.md",
        release_dir / "1.5.0.md",
    )


def test_update_release_baseline_is_deterministic(tmp_path: Path) -> None:
    module = _load_module()
    _copy_release_truth_fixture(tmp_path)

    arguments = {
        "mcp_version": "1.5.0",
        "npm_version": "1.5.0",
        "studio_version": "1.4.0",
        "reviewed_at": "2026-07-21",
    }
    module.update_release_baseline(tmp_path, **arguments)
    first = {
        path.relative_to(tmp_path): path.read_text(encoding="utf-8")
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    module.update_release_baseline(tmp_path, **arguments)
    second = {
        path.relative_to(tmp_path): path.read_text(encoding="utf-8")
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert second == first
    manifest = json.loads((tmp_path / "release-baseline.json").read_text(encoding="utf-8"))
    assert manifest["published_release"] == "1.5.0"
    assert manifest["reviewed_at"] == "2026-07-21"
    versions = {item["id"]: item["version"] for item in manifest["packages"]}
    assert versions == {"python": "1.5.0", "npm": "1.5.0", "studio": "1.4.0"}

    studio = next(item for item in manifest["packages"] if item["id"] == "studio")
    assert studio["status"] == "Published on VS Marketplace and Open VSX"
    assert "registry-verification-studio.json" in studio["evidence"]

    for relative in ("ROADMAP.md", "RELEASE_NOTES.md", "docs/release-notes/1.5.0.md"):
        text = (tmp_path / relative).read_text(encoding="utf-8")
        assert "| `1.5.0` | Published on PyPI |" in text
        assert "| `1.4.0` | Published on VS Marketplace and Open VSX |" in text
    assert "Fovux 1.5.0 is the current reviewed release baseline" in (
        tmp_path / "RELEASE_NOTES.md"
    ).read_text(encoding="utf-8")
    root_readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "Python backend package `fovux-mcp` 1.5.0" in root_readme
    assert "npm wrapper `fovux-mcp` 1.5.0" in root_readme
    assert "VS Code companion `Fovux Studio` 1.4.0" in root_readme
    assert "Fovux MCP 1.5.0 exposes 47 local tools" in root_readme
    assert "Fovux MCP 1.5.0 currently exposes 47 local tools" in (
        tmp_path / "fovux-mcp" / "README.md"
    ).read_text(encoding="utf-8")


def test_update_release_baseline_rejects_path_escape_version(tmp_path: Path) -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="numeric semantic versioning"):
        module.update_release_baseline(
            tmp_path,
            mcp_version="../1.5.0",
            npm_version="1.5.0",
            studio_version="1.4.0",
            reviewed_at="2026-07-21",
        )
