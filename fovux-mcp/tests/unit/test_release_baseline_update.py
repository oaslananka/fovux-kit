"""Tests for deterministic post-release baseline synchronization."""

from __future__ import annotations

import importlib.util
import json
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


def _release_documents() -> dict[str, str]:
    return {
        "README.md": (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
        "fovux-mcp/README.md": (REPO_ROOT / "fovux-mcp" / "README.md").read_text(encoding="utf-8"),
        "ROADMAP.md": (REPO_ROOT / "ROADMAP.md").read_text(encoding="utf-8"),
        "RELEASE_NOTES.md": (REPO_ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8"),
        "published_release_note": (REPO_ROOT / "docs" / "release-notes" / "1.5.0.md").read_text(
            encoding="utf-8"
        ),
    }


def test_synchronize_release_content_is_deterministic() -> None:
    module = _load_module()
    arguments = {
        "mcp_version": "1.5.0",
        "npm_version": "1.5.0",
        "studio_version": "1.4.0",
        "reviewed_at": "2026-07-21",
    }
    manifest_text = (REPO_ROOT / "release-baseline.json").read_text(encoding="utf-8")
    documents = _release_documents()

    first_manifest, first_documents = module.synchronize_release_content(
        manifest_text, documents, **arguments
    )
    second_manifest, second_documents = module.synchronize_release_content(
        first_manifest, first_documents, **arguments
    )

    assert second_manifest == first_manifest
    assert second_documents == first_documents
    manifest = json.loads(first_manifest)
    assert manifest["published_release"] == "1.5.0"
    assert manifest["reviewed_at"] == "2026-07-21"
    versions = {item["id"]: item["version"] for item in manifest["packages"]}
    assert versions == {"python": "1.5.0", "npm": "1.5.0", "studio": "1.4.0"}

    studio = next(item for item in manifest["packages"] if item["id"] == "studio")
    assert studio["status"] == "Published on VS Marketplace and Open VSX"
    assert "registry-verification-studio.json" in studio["evidence"]

    for label in ("ROADMAP.md", "RELEASE_NOTES.md", "published_release_note"):
        text = first_documents[label]
        assert "| `1.5.0` | Published on PyPI |" in text
        assert "| `1.4.0` | Published on VS Marketplace and Open VSX |" in text
    assert (
        "Fovux 1.5.0 is the current reviewed release baseline"
        in first_documents["RELEASE_NOTES.md"]
    )
    assert "Python backend package `fovux-mcp` 1.5.0" in first_documents["README.md"]
    assert "npm wrapper `fovux-mcp` 1.5.0" in first_documents["README.md"]
    assert "VS Code companion `Fovux Studio` 1.4.0" in first_documents["README.md"]
    assert "Fovux MCP 1.5.0 exposes 47 local tools" in first_documents["README.md"]
    assert (
        "Fovux MCP 1.5.0 currently exposes 47 local tools" in first_documents["fovux-mcp/README.md"]
    )


def test_synchronize_release_content_rejects_path_escape_version() -> None:
    module = _load_module()

    with pytest.raises(ValueError, match="numeric semantic versioning"):
        module.synchronize_release_content(
            "{}",
            {},
            mcp_version="../1.5.0",
            npm_version="1.5.0",
            studio_version="1.4.0",
            reviewed_at="2026-07-21",
        )


def test_repository_paths_are_fixed_and_release_note_is_existing() -> None:
    module = _load_module()

    assert module.MANIFEST_PATH == REPO_ROOT / "release-baseline.json"
    assert module.ROOT_RELEASE_NOTES_PATH == REPO_ROOT / "RELEASE_NOTES.md"
    assert module._repository_versions() == ("1.5.0", "1.5.0", "1.4.0")
    release_note = module._published_release_note("1.5.0")
    assert release_note == REPO_ROOT / "docs" / "release-notes" / "1.5.0.md"
    assert release_note.is_file()
    assert not release_note.is_symlink()
    assert release_note.parent == module.RELEASE_NOTES_DIRECTORY.resolve()
