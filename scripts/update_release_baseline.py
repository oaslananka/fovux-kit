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


def _replace_marked_table(path: Path, table: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.find(BASELINE_START)
    end = text.find(BASELINE_END, start)
    if start < 0 or end < start:
        raise ValueError(f"{path} is missing release baseline markers")
    end += len(BASELINE_END)
    path.write_text(text[:start] + table + text[end:], encoding="utf-8")


def _replace_baseline_phrase(path: Path, version: str) -> None:
    text = path.read_text(encoding="utf-8")
    replacement = f"Fovux {version} is the current reviewed release baseline"
    updated, count = BASELINE_PHRASE.subn(replacement, text, count=1)
    if count != 1:
        raise ValueError(f"{path} is missing the reviewed baseline phrase")
    path.write_text(updated, encoding="utf-8")


def _replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1)
    if count != 1:
        raise ValueError(f"{path} does not match expected release metadata: {pattern}")
    path.write_text(updated, encoding="utf-8")


def _update_readmes(
    root: Path,
    *,
    mcp_version: str,
    npm_version: str,
    studio_version: str,
    backend_tools: int,
) -> list[Path]:
    root_readme = root / "README.md"
    mcp_readme = root / "fovux-mcp" / "README.md"
    _replace_once(
        root_readme,
        r"Python backend package `fovux-mcp` \d+\.\d+\.\d+",
        f"Python backend package `fovux-mcp` {mcp_version}",
    )
    _replace_once(
        root_readme,
        r"npm wrapper `fovux-mcp` \d+\.\d+\.\d+",
        f"npm wrapper `fovux-mcp` {npm_version}",
    )
    _replace_once(
        root_readme,
        r"VS Code companion `Fovux Studio` \d+\.\d+\.\d+",
        f"VS Code companion `Fovux Studio` {studio_version}",
    )
    _replace_once(
        root_readme,
        r"Fovux MCP \d+\.\d+\.\d+ exposes \d+ local tools",
        f"Fovux MCP {mcp_version} exposes {backend_tools} local tools",
    )
    _replace_once(
        mcp_readme,
        r"Fovux MCP \d+\.\d+\.\d+ currently exposes \d+ local tools",
        f"Fovux MCP {mcp_version} currently exposes {backend_tools} local tools",
    )
    return [root_readme, mcp_readme]


def update_release_baseline(
    root: Path,
    *,
    mcp_version: str,
    npm_version: str,
    studio_version: str,
    reviewed_at: str,
) -> list[Path]:
    """Update the manifest and generated release-truth documents deterministically."""
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

    manifest_path = root / "release-baseline.json"
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
    release_note = root / "docs" / "release-notes" / f"{mcp_version}.md"
    documents = [root / "ROADMAP.md", root / "RELEASE_NOTES.md", release_note]
    for path in documents:
        _replace_marked_table(path, table)
    for path in (root / "RELEASE_NOTES.md", release_note):
        _replace_baseline_phrase(path, mcp_version)

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
