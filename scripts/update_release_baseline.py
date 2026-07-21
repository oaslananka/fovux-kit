"""Synchronize the reviewed published-release baseline after registry verification."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from check_release_truth import BASELINE_END, BASELINE_START, render_release_table

ROOT = Path(__file__).resolve().parent.parent
BASELINE_PHRASE = re.compile(
    r"Fovux \d+\.\d+\.\d+ is the current reviewed release baseline"
)
VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")
STATIC_EDITABLE_FILES = frozenset(
    {
        "README.md",
        "fovux-mcp/README.md",
        "ROADMAP.md",
        "RELEASE_NOTES.md",
        "release-baseline.json",
    }
)
RELEASE_NOTE_PATTERN = re.compile(r"docs/release-notes/\d+\.\d+\.\d+\.md")


def _load_manifest(root: Path) -> dict[str, Any]:
    value = json.loads((root / "release-baseline.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("release-baseline.json must contain a JSON object")
    return value


def _package(manifest: dict[str, Any], package_id: str) -> dict[str, Any]:
    packages = manifest.get("packages")
    if not isinstance(packages, list):
        raise ValueError("release-baseline.json packages must be an array")
    for item in packages:
        if isinstance(item, dict) and item.get("id") == package_id:
            return item
    raise ValueError(f"release-baseline.json is missing package id {package_id!r}")


def _validated_document(root: Path, relative: str) -> Path:
    """Resolve one allowlisted release-truth document inside the repository root."""
    if relative not in STATIC_EDITABLE_FILES and not RELEASE_NOTE_PATTERN.fullmatch(
        relative
    ):
        raise ValueError(f"release baseline updater does not allow path {relative!r}")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(
            "release baseline document resolves outside the repository"
        ) from exc
    if not candidate.is_file():
        raise ValueError(f"release baseline document does not exist: {relative}")
    return candidate


def _validate_versions(*versions: str) -> None:
    for version in versions:
        if not VERSION_PATTERN.fullmatch(version):
            raise ValueError(
                f"release version must use numeric semantic versioning: {version!r}"
            )


def _replace_marked_table(root: Path, relative: str, table: str) -> Path:
    path = _validated_document(root, relative)
    text = path.read_text(encoding="utf-8")
    start = text.find(BASELINE_START)
    end = text.find(BASELINE_END, start)
    if start < 0 or end < start:
        raise ValueError(f"{path} is missing release baseline markers")
    end += len(BASELINE_END)
    path.write_text(text[:start] + table + text[end:], encoding="utf-8")
    return path


def _replace_baseline_phrase(root: Path, relative: str, version: str) -> Path:
    path = _validated_document(root, relative)
    text = path.read_text(encoding="utf-8")
    replacement = f"Fovux {version} is the current reviewed release baseline"
    updated, count = BASELINE_PHRASE.subn(replacement, text, count=1)
    if count != 1:
        raise ValueError(f"{path} is missing the reviewed baseline phrase")
    path.write_text(updated, encoding="utf-8")
    return path


def _replace_once(root: Path, relative: str, pattern: str, replacement: str) -> Path:
    path = _validated_document(root, relative)
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise ValueError(f"{path} does not match expected release metadata: {pattern}")
    path.write_text(updated, encoding="utf-8")
    return path


def _update_readmes(
    root: Path,
    *,
    mcp_version: str,
    npm_version: str,
    studio_version: str,
    backend_tools: int,
) -> list[Path]:
    root_readme = "README.md"
    mcp_readme = "fovux-mcp/README.md"
    _replace_once(
        root,
        root_readme,
        r"Python backend package `fovux-mcp` \d+\.\d+\.\d+",
        f"Python backend package `fovux-mcp` {mcp_version}",
    )
    _replace_once(
        root,
        root_readme,
        r"npm wrapper `fovux-mcp` \d+\.\d+\.\d+",
        f"npm wrapper `fovux-mcp` {npm_version}",
    )
    _replace_once(
        root,
        root_readme,
        r"VS Code companion `Fovux Studio` \d+\.\d+\.\d+",
        f"VS Code companion `Fovux Studio` {studio_version}",
    )
    _replace_once(
        root,
        root_readme,
        r"Fovux MCP \d+\.\d+\.\d+ exposes \d+ local tools",
        f"Fovux MCP {mcp_version} exposes {backend_tools} local tools",
    )
    _replace_once(
        root,
        mcp_readme,
        r"Fovux MCP \d+\.\d+\.\d+ currently exposes \d+ local tools",
        f"Fovux MCP {mcp_version} currently exposes {backend_tools} local tools",
    )
    return [
        _validated_document(root, root_readme),
        _validated_document(root, mcp_readme),
    ]


def update_release_baseline(
    root: Path,
    *,
    mcp_version: str,
    npm_version: str,
    studio_version: str,
    reviewed_at: str,
) -> list[Path]:
    """Update the manifest and generated release-truth documents deterministically."""
    _validate_versions(mcp_version, npm_version, studio_version)
    date.fromisoformat(reviewed_at)
    manifest = _load_manifest(root)
    manifest["reviewed_at"] = reviewed_at
    manifest["published_release"] = mcp_version

    python_package = _package(manifest, "python")
    python_package.update(
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

    npm_package = _package(manifest, "npm")
    npm_package.update(
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

    studio_package = _package(manifest, "studio")
    studio_package.update(
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

    manifest_path = _validated_document(root, "release-baseline.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    tooling = manifest.get("tooling")
    if not isinstance(tooling, dict) or not isinstance(
        tooling.get("backend_tools"), int
    ):
        raise ValueError(
            "release-baseline.json tooling.backend_tools must be an integer"
        )
    readmes = _update_readmes(
        root,
        mcp_version=mcp_version,
        npm_version=npm_version,
        studio_version=studio_version,
        backend_tools=tooling["backend_tools"],
    )

    table = render_release_table(manifest)
    release_note = f"docs/release-notes/{mcp_version}.md"
    document_names = ["ROADMAP.md", "RELEASE_NOTES.md", release_note]
    documents = [_replace_marked_table(root, name, table) for name in document_names]
    for name in ("RELEASE_NOTES.md", release_note):
        _replace_baseline_phrase(root, name, mcp_version)

    return [manifest_path, *readmes, *documents]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mcp-version", required=True)
    parser.add_argument("--npm-version", required=True)
    parser.add_argument("--studio-version", required=True)
    parser.add_argument("--reviewed-at", default=date.today().isoformat())
    return parser.parse_args()


def main() -> int:
    """Update the checked-out repository's release baseline."""
    args = _parse_args()
    paths = update_release_baseline(
        ROOT,
        mcp_version=args.mcp_version,
        npm_version=args.npm_version,
        studio_version=args.studio_version,
        reviewed_at=args.reviewed_at,
    )
    print("Updated release baseline files:")
    for path in paths:
        print(f"- {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
