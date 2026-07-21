"""Tests for semantic published-release and milestone truth."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_release_truth.py"


def _load_module() -> ModuleType:
    assert SCRIPT_PATH.exists(), "release truth checker is missing"
    spec = importlib.util.spec_from_file_location("check_release_truth", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repository_release_truth_is_valid() -> None:
    module = _load_module()

    assert module.validate_release_truth(REPO_ROOT) == []


def _write_package_versions(root: Path, *, mcp: str, npm: str, studio: str) -> None:
    (root / "fovux-mcp").mkdir(exist_ok=True)
    (root / "fovux-mcp-npm").mkdir(exist_ok=True)
    (root / "fovux-studio").mkdir(exist_ok=True)
    (root / "fovux-mcp" / "pyproject.toml").write_text(
        f'[project]\nname = "fovux-mcp"\nversion = "{mcp}"\n', encoding="utf-8"
    )
    (root / "fovux-mcp-npm" / "package.json").write_text(
        json.dumps({"version": npm}), encoding="utf-8"
    )
    (root / "fovux-studio" / "package.json").write_text(
        json.dumps({"version": studio}), encoding="utf-8"
    )


def test_stale_package_fact_is_rejected(tmp_path: Path) -> None:
    module = _load_module()
    manifest = {
        "schema_version": 1,
        "reviewed_at": "2026-07-20",
        "published_release": "1.4.0",
        "packages": [
            {
                "id": "python",
                "component": "Python package `fovux-mcp`",
                "version": "1.4.0",
                "status": "Published on PyPI",
                "evidence": ["wheel.whl", "source.tar.gz"],
            }
        ],
        "milestones": [],
    }
    (tmp_path / "release-baseline.json").write_text(json.dumps(manifest), encoding="utf-8")
    _write_package_versions(tmp_path, mcp="1.4.0", npm="1.4.0", studio="1.3.0")
    stale_table = """<!-- release-baseline:start -->
| Component | Published version | Channel status | Evidence |
| --- | --- | --- | --- |
| Python package `fovux-mcp` | `1.3.0` | Published on PyPI | `wheel.whl`, `source.tar.gz` |
<!-- release-baseline:end -->
"""
    (tmp_path / "ROADMAP.md").write_text(stale_table, encoding="utf-8")
    (tmp_path / "RELEASE_NOTES.md").write_text(stale_table, encoding="utf-8")
    release_dir = tmp_path / "docs" / "release-notes"
    release_dir.mkdir(parents=True)
    (release_dir / "1.4.0.md").write_text(stale_table, encoding="utf-8")

    errors = module.validate_release_truth(tmp_path)

    assert any("ROADMAP.md" in error and "generated baseline table" in error for error in errors)
    assert any("1.3.0" in (tmp_path / "ROADMAP.md").read_text() for _ in [0])


def test_release_candidate_documents_are_valid_before_publication(tmp_path: Path) -> None:
    module = _load_module()
    manifest = {
        "schema_version": 1,
        "reviewed_at": "2026-07-20",
        "published_release": "1.5.0",
        "packages": [
            {
                "id": "python",
                "component": "Python package `fovux-mcp`",
                "version": "1.5.0",
                "status": "Published on PyPI",
                "evidence": ["wheel.whl"],
            },
            {
                "id": "npm",
                "component": "npm wrapper `fovux-mcp`",
                "version": "1.5.0",
                "status": "Published on npm",
                "evidence": ["registry.json"],
            },
            {
                "id": "studio",
                "component": "VS Code extension `oaslananka.fovuxstudiokit`",
                "version": "1.4.0",
                "status": "Published on VS Marketplace and Open VSX",
                "evidence": ["studio.json"],
            },
        ],
        "milestones": [],
    }
    (tmp_path / "release-baseline.json").write_text(json.dumps(manifest), encoding="utf-8")
    _write_package_versions(tmp_path, mcp="1.6.0", npm="1.6.0", studio="1.5.0")
    published_table = module.render_release_table(manifest)
    (tmp_path / "ROADMAP.md").write_text(published_table, encoding="utf-8")
    release_dir = tmp_path / "docs" / "release-notes"
    release_dir.mkdir(parents=True)
    (release_dir / "1.5.0.md").write_text(
        "Fovux 1.5.0 is the current reviewed release baseline.\n" + published_table,
        encoding="utf-8",
    )
    candidate = """# Fovux 1.6.0 Release Notes

Fovux 1.6.0 is the current release candidate for validation.

<!-- release-baseline:start -->
| Component | Candidate version | Channel status | Evidence |
| --- | --- | --- | --- |
| Python package `fovux-mcp` | `1.6.0` | Pending publication | Generated later |
| npm wrapper `fovux-mcp` | `1.6.0` | Pending publication | Generated later |
| VS Code extension `oaslananka.fovuxstudiokit` | `1.5.0` | Pending publication | Generated later |
<!-- release-baseline:end -->
"""
    (tmp_path / "RELEASE_NOTES.md").write_text(candidate, encoding="utf-8")
    (release_dir / "1.6.0.md").write_text(candidate, encoding="utf-8")

    assert module.validate_release_truth(tmp_path) == []
