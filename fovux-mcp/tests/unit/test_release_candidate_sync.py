"""Regression tests for release-candidate notes and post-release baseline automation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
SYNC_SCRIPT = SCRIPTS / "sync_mcp_metadata.py"


def _load_sync_module() -> ModuleType:
    sys.path.insert(0, str(SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location("sync_mcp_metadata", SYNC_SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(SCRIPTS))


def test_candidate_notes_use_target_versions_and_changelog_sections() -> None:
    module = _load_sync_module()
    changelogs = {
        "mcp": """# Changelog

## [1.6.0] (2026-07-21)

### Features

* Generate LM tools.

## [1.5.0]

Old.
""",
        "npm": """# Changelog

## [1.6.0] (2026-07-21)

### Chores

* Synchronize versions.
""",
        "studio": """# Changelog

## [1.5.0] (2026-07-21)

### Features

* Generate LM tools.
""",
    }

    rendered = module.render_candidate_release_notes(
        mcp_version="1.6.0",
        npm_version="1.6.0",
        studio_version="1.5.0",
        changelogs=changelogs,
    )

    assert rendered.startswith("# Fovux 1.6.0 Release Notes\n")
    assert "Fovux 1.6.0 is the current release candidate" in rendered
    assert "current reviewed release baseline" not in rendered
    assert "| Python package `fovux-mcp` | `1.6.0` | Pending publication |" in rendered
    assert "| npm wrapper `fovux-mcp` | `1.6.0` | Pending publication |" in rendered
    assert (
        "| VS Code extension `oaslananka.fovuxstudiokit` | `1.5.0` | Pending publication |"
        in rendered
    )
    assert "- Generate LM tools." in rendered
    assert "- Synchronize versions." in rendered
    assert "Old." not in rendered


def test_partial_candidate_keeps_unchanged_studio_published() -> None:
    module = _load_sync_module()
    changelogs = {
        "mcp": "# Changelog\n\n## [1.6.2]\n\n### Fixes\n\n* Compatibility fix.\n",
        "npm": "# Changelog\n\n## [1.6.2]\n\n### Chores\n\n* Wrapper sync.\n",
        "studio": "# Changelog\n\n## [1.5.1]\n\n### Fixes\n\n* Previous fix.\n",
    }
    published_packages = {
        "python": {
            "version": "1.6.1",
            "status": "Published on PyPI",
            "evidence": ["python evidence"],
        },
        "npm": {
            "version": "1.6.1",
            "status": "Published on npm",
            "evidence": ["npm evidence"],
        },
        "studio": {
            "version": "1.5.1",
            "status": "Published on VS Marketplace and Open VSX",
            "evidence": ["studio evidence"],
        },
    }

    rendered = module.render_candidate_release_notes(
        mcp_version="1.6.2",
        npm_version="1.6.2",
        studio_version="1.5.1",
        changelogs=changelogs,
        published_packages=published_packages,
    )

    assert "| Python package `fovux-mcp` | `1.6.2` | Pending publication |" in rendered
    assert "| npm wrapper `fovux-mcp` | `1.6.2` | Pending publication |" in rendered
    assert (
        "| VS Code extension `oaslananka.fovuxstudiokit` | `1.5.1` | "
        "Published on VS Marketplace and Open VSX | `studio evidence` |"
    ) in rendered
    assert "### Fovux Studio 1.5.1" not in rendered
    assert "Previous fix." not in rendered
    assert "marketplace publication" not in rendered


def test_published_baseline_is_not_treated_as_a_candidate(tmp_path: Path) -> None:
    module = _load_sync_module()
    (tmp_path / "release-baseline.json").write_text(
        '{"published_release": "1.6.0"}\n', encoding="utf-8"
    )

    assert module._is_unpublished_candidate(tmp_path, "1.6.0") is False
    assert module._is_unpublished_candidate(tmp_path, "1.6.1") is True


def test_sync_docs_replaces_stale_candidate_content(tmp_path: Path) -> None:
    module = _load_sync_module()
    (tmp_path / "fovux-mcp").mkdir()
    (tmp_path / "fovux-mcp-npm").mkdir()
    (tmp_path / "fovux-studio").mkdir()
    (tmp_path / "docs" / "release-notes").mkdir(parents=True)
    (tmp_path / "CHANGELOG.md").write_text("# Changelog\n\n## [1.5.0]\n\nOld.\n", encoding="utf-8")
    (tmp_path / "RELEASE_NOTES.md").write_text(
        "# Fovux 1.5.0 Release Notes\n\nFovux 1.5.0 is the current reviewed release baseline.\n",
        encoding="utf-8",
    )
    (tmp_path / "fovux-mcp" / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.6.0]\n\n### Fixes\n\n* Backend fix.\n",
        encoding="utf-8",
    )
    (tmp_path / "fovux-mcp-npm" / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.6.0]\n\n### Chores\n\n* Wrapper sync.\n",
        encoding="utf-8",
    )
    (tmp_path / "fovux-studio" / "CHANGELOG.md").write_text(
        "# Changelog\n\n## [1.5.0]\n\n### Features\n\n* Studio feature.\n",
        encoding="utf-8",
    )

    assert module._sync_docs(tmp_path, "1.6.0", "1.6.0", "1.5.0") is True
    expected = (tmp_path / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    candidate = tmp_path / "docs" / "release-notes" / "1.6.0.md"
    assert candidate.read_text(encoding="utf-8") == expected
    assert "current release candidate" in expected
    assert "Backend fix." in expected
    assert module._sync_docs(tmp_path, "1.6.0", "1.6.0", "1.5.0") is False


def test_studio_verification_allows_marketplace_propagation() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-please.yml").read_text(encoding="utf-8")

    assert "--channel studio --retries 40 --delay 15" in workflow


def test_release_workflow_opens_post_release_baseline_pr() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release-please.yml").read_text(encoding="utf-8")
    for required in (
        "post-release-baseline:",
        "needs.verify-release.result == 'success'",
        "python scripts/update_release_baseline.py",
        "chore/post-release-baseline-",
        "secrets.RELEASE_PLEASE_TOKEN",
        "gh pr create",
    ):
        assert required in workflow
