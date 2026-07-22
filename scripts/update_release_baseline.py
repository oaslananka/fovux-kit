"""Synchronize the reviewed published-release baseline after registry verification."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from collections.abc import Mapping
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

from check_release_truth import BASELINE_END, BASELINE_START, render_release_table

ROOT = Path(__file__).resolve().parent.parent
BASELINE_FILENAME = "release-baseline.json"
ROOT_README_FILENAME = "README.md"
MCP_README_FILENAME = "fovux-mcp/README.md"
ROADMAP_FILENAME = "ROADMAP.md"
ROOT_RELEASE_NOTES_FILENAME = "RELEASE_NOTES.md"
PUBLISHED_RELEASE_NOTE_KEY = "published_release_note"

MANIFEST_PATH = ROOT / BASELINE_FILENAME
ROOT_README_PATH = ROOT / ROOT_README_FILENAME
MCP_README_PATH = ROOT / MCP_README_FILENAME
ROADMAP_PATH = ROOT / ROADMAP_FILENAME
ROOT_RELEASE_NOTES_PATH = ROOT / ROOT_RELEASE_NOTES_FILENAME
RELEASE_NOTES_DIRECTORY = ROOT / "docs" / "release-notes"
MCP_PYPROJECT_PATH = ROOT / "fovux-mcp" / "pyproject.toml"
NPM_PACKAGE_PATH = ROOT / "fovux-mcp-npm" / "package.json"
STUDIO_PACKAGE_PATH = ROOT / "fovux-studio" / "package.json"

BASELINE_PHRASE = re.compile(
    r"Fovux \d+\.\d+\.\d+ is the current "
    r"(?:reviewed release baseline|release candidate)"
)
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")


def _load_manifest_text(text: str) -> dict[str, Any]:
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError(f"{BASELINE_FILENAME} must contain a JSON object")
    return value


def _package(manifest: dict[str, Any], package_id: str) -> dict[str, Any]:
    packages = manifest.get("packages")
    if not isinstance(packages, list):
        raise ValueError(f"{BASELINE_FILENAME} packages must be an array")
    for item in packages:
        if isinstance(item, dict) and item.get("id") == package_id:
            return item
    raise ValueError(f"{BASELINE_FILENAME} is missing package id {package_id!r}")


def _validate_versions(*versions: str) -> None:
    for version in versions:
        if not VERSION_PATTERN.fullmatch(version):
            raise ValueError(f"release version must use numeric semantic versioning: {version!r}")


def _repository_versions() -> tuple[str, str, str]:
    """Read released package versions from fixed repository manifests."""
    mcp_config = tomllib.loads(MCP_PYPROJECT_PATH.read_text(encoding="utf-8"))
    mcp_version = str(mcp_config["project"]["version"])
    npm_version = str(json.loads(NPM_PACKAGE_PATH.read_text(encoding="utf-8"))["version"])
    studio_version = str(json.loads(STUDIO_PACKAGE_PATH.read_text(encoding="utf-8"))["version"])
    _validate_versions(mcp_version, npm_version, studio_version)
    return mcp_version, npm_version, studio_version


def _updated_marked_table(text: str, table: str, *, label: str) -> str:
    start = text.find(BASELINE_START)
    end = text.find(BASELINE_END, start)
    if start < 0 or end < start:
        raise ValueError(f"{label} is missing release baseline markers")
    end += len(BASELINE_END)
    return text[:start] + table + text[end:]


def _updated_baseline_phrase(text: str, version: str, *, label: str) -> str:
    replacement = f"Fovux {version} is the current reviewed release baseline"
    updated, count = BASELINE_PHRASE.subn(replacement, text, count=1)
    if count != 1:
        raise ValueError(f"{label} is missing the reviewed baseline phrase")
    return updated


def _updated_once(text: str, pattern: str, replacement: str, *, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise ValueError(f"{label} does not match expected release metadata")
    return updated


def _updated_publication_wording(text: str, *, label: str) -> str:
    """Promote candidate-only publication wording to verified release truth."""
    updated = _updated_once(
        text,
        (
            r"(?:Package publication (?:remains pending until the release workflow verifies|"
            r"has been verified by the release workflow across) every configured\s+"
            r"registry and extension marketplace|"
            r"Publication (?:remains pending only for the changed packages identified below; "
            r"unchanged\s+components retain their previously verified release status|"
            r"has been verified by the release workflow for every changed package; unchanged\s+"
            r"components retain their previously verified release status))\."
        ),
        (
            "Publication has been verified by the release workflow for every changed package; "
            "unchanged\ncomponents retain their previously verified release status."
        ),
        label=label,
    )
    return _updated_once(
        updated,
        (
            r"(?:The final GitHub Release evidence(?: for changed packages)? will include|"
            r"The verified GitHub Release evidence includes):"
        ),
        "The verified GitHub Release evidence includes:",
        label=label,
    )


def _update_manifest(
    source: Mapping[str, Any],
    *,
    mcp_version: str,
    npm_version: str,
    studio_version: str,
    reviewed_at: str,
) -> dict[str, Any]:
    manifest = deepcopy(dict(source))
    manifest["reviewed_at"] = reviewed_at
    manifest["published_release"] = mcp_version

    _package(manifest, "python").update(
        {
            "version": mcp_version,
            "status": "Published on PyPI",
            "evidence": [
                f"fovux_mcp-{mcp_version}-py3-none-any.whl",
                f"fovux_mcp-{mcp_version}.tar.gz",
                "fovux-mcp-sbom.spdx.json",
                "fovux-mcp.sha256",
                "registry-verification-python.json",
            ],
        }
    )
    _package(manifest, "npm").update(
        {
            "version": npm_version,
            "status": "Published on npm",
            "evidence": [
                "npm registry metadata",
                "wrapper CLI smoke result",
                f"fovux-mcp-npm-v{npm_version} source release",
                "registry-verification-npm.json",
            ],
        }
    )
    _package(manifest, "studio").update(
        {
            "version": studio_version,
            "status": "Published on VS Marketplace and Open VSX",
            "evidence": [
                "fovuxstudiokit.vsix",
                "fovux-studio-sbom.spdx.json",
                "fovux-studio.sha256",
                "registry-verification-studio.json",
            ],
        }
    )
    return manifest


def synchronize_release_content(
    manifest_text: str,
    documents: Mapping[str, str],
    *,
    mcp_version: str,
    npm_version: str,
    studio_version: str,
    reviewed_at: str,
) -> tuple[str, dict[str, str]]:
    """Return deterministic manifest and document content without filesystem access."""
    _validate_versions(mcp_version, npm_version, studio_version)
    date.fromisoformat(reviewed_at)

    manifest = _update_manifest(
        _load_manifest_text(manifest_text),
        mcp_version=mcp_version,
        npm_version=npm_version,
        studio_version=studio_version,
        reviewed_at=reviewed_at,
    )
    tooling = manifest.get("tooling")
    if not isinstance(tooling, dict) or not isinstance(tooling.get("backend_tools"), int):
        raise ValueError(f"{BASELINE_FILENAME} tooling.backend_tools must be an integer")
    backend_tools = tooling["backend_tools"]

    required = {
        ROOT_README_FILENAME,
        MCP_README_FILENAME,
        ROADMAP_FILENAME,
        ROOT_RELEASE_NOTES_FILENAME,
        PUBLISHED_RELEASE_NOTE_KEY,
    }
    missing = sorted(required - documents.keys())
    if missing:
        raise ValueError(f"release baseline documents are missing: {missing}")

    updated = dict(documents)
    root_readme = updated[ROOT_README_FILENAME]
    root_readme = _updated_once(
        root_readme,
        r"Python backend package `fovux-mcp` \d+\.\d+\.\d+",
        f"Python backend package `fovux-mcp` {mcp_version}",
        label=ROOT_README_FILENAME,
    )
    root_readme = _updated_once(
        root_readme,
        r"npm wrapper `fovux-mcp` \d+\.\d+\.\d+",
        f"npm wrapper `fovux-mcp` {npm_version}",
        label=ROOT_README_FILENAME,
    )
    root_readme = _updated_once(
        root_readme,
        r"VS Code companion `Fovux Studio` \d+\.\d+\.\d+",
        f"VS Code companion `Fovux Studio` {studio_version}",
        label=ROOT_README_FILENAME,
    )
    updated[ROOT_README_FILENAME] = _updated_once(
        root_readme,
        r"Fovux MCP \d+\.\d+\.\d+ exposes \d+ local tools",
        f"Fovux MCP {mcp_version} exposes {backend_tools} local tools",
        label=ROOT_README_FILENAME,
    )
    updated[MCP_README_FILENAME] = _updated_once(
        updated[MCP_README_FILENAME],
        r"Fovux MCP \d+\.\d+\.\d+ currently exposes \d+ local tools",
        f"Fovux MCP {mcp_version} currently exposes {backend_tools} local tools",
        label=MCP_README_FILENAME,
    )

    table = render_release_table(manifest)
    for label in (
        ROADMAP_FILENAME,
        ROOT_RELEASE_NOTES_FILENAME,
        PUBLISHED_RELEASE_NOTE_KEY,
    ):
        updated[label] = _updated_marked_table(updated[label], table, label=label)
    for label in (ROOT_RELEASE_NOTES_FILENAME, "published_release_note"):
        published = _updated_baseline_phrase(updated[label], mcp_version, label=label)
        updated[label] = _updated_publication_wording(published, label=label)

    return json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", updated


def _published_release_note(version: str) -> Path:
    """Select an existing release-note file without constructing a path from input."""
    expected_heading = f"# Fovux {version} Release Notes"
    matches = [
        candidate
        for candidate in RELEASE_NOTES_DIRECTORY.glob("*.md")
        if candidate.is_file()
        and candidate.read_text(encoding="utf-8").startswith(expected_heading)
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one published release note for {version}, found {len(matches)}"
        )
    selected = matches[0]
    resolved_directory = RELEASE_NOTES_DIRECTORY.resolve()
    resolved_selected = selected.resolve()
    if selected.is_symlink() or resolved_selected.parent != resolved_directory:
        raise ValueError(
            "published release note must be a regular file in the release-note directory"
        )
    return resolved_selected


def update_repository_baseline(*, reviewed_at: str) -> list[Path]:
    """Apply synchronized content to fixed, repository-owned release-truth files."""
    mcp_version, npm_version, studio_version = _repository_versions()
    release_note_path = _published_release_note(mcp_version)
    documents = {
        ROOT_README_FILENAME: ROOT_README_PATH.read_text(encoding="utf-8"),
        MCP_README_FILENAME: MCP_README_PATH.read_text(encoding="utf-8"),
        ROADMAP_FILENAME: ROADMAP_PATH.read_text(encoding="utf-8"),
        ROOT_RELEASE_NOTES_FILENAME: ROOT_RELEASE_NOTES_PATH.read_text(encoding="utf-8"),
        "published_release_note": release_note_path.read_text(encoding="utf-8"),
    }
    manifest_text, updated = synchronize_release_content(
        MANIFEST_PATH.read_text(encoding="utf-8"),
        documents,
        mcp_version=mcp_version,
        npm_version=npm_version,
        studio_version=studio_version,
        reviewed_at=reviewed_at,
    )

    MANIFEST_PATH.write_text(manifest_text, encoding="utf-8")
    ROOT_README_PATH.write_text(updated[ROOT_README_FILENAME], encoding="utf-8")
    MCP_README_PATH.write_text(updated[MCP_README_FILENAME], encoding="utf-8")
    ROADMAP_PATH.write_text(updated[ROADMAP_FILENAME], encoding="utf-8")
    ROOT_RELEASE_NOTES_PATH.write_text(updated[ROOT_RELEASE_NOTES_FILENAME], encoding="utf-8")
    # The path is an existing, non-symlink file selected from the fixed release-note directory.
    release_note_path.write_text(  # NOSONAR -- containment is enforced by _published_release_note
        updated[PUBLISHED_RELEASE_NOTE_KEY], encoding="utf-8"
    )

    return [
        MANIFEST_PATH,
        ROOT_README_PATH,
        MCP_README_PATH,
        ROADMAP_PATH,
        ROOT_RELEASE_NOTES_PATH,
        release_note_path,
    ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed-at", default=date.today().isoformat())
    return parser.parse_args()


def main() -> int:
    """Update the checked-out repository's release baseline."""
    args = _parse_args()
    paths = update_repository_baseline(reviewed_at=args.reviewed_at)
    print("Updated release baseline files:")
    for path in paths:
        print(f"- {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
