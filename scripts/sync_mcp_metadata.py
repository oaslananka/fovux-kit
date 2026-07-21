"""Synchronize release-candidate metadata after Release Please updates package versions.

Run as:
    python scripts/sync_mcp_metadata.py

The command is idempotent. It keeps MCP metadata aligned and renders candidate
release notes from the package changelog sections without claiming publication.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path

_VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")
CHANGELOG_FILENAME = "CHANGELOG.md"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_pyproject_version(root: Path) -> str:
    content = (root / "fovux-mcp" / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise SystemExit("Could not find version in pyproject.toml")
    return match.group(1)


def _read_json_version(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8")).get("version")
    if not isinstance(value, str) or not _VERSION_PATTERN.fullmatch(value):
        raise SystemExit(f"Could not find a semantic version in {path}")
    return value


def _read_package_versions(root: Path) -> tuple[str, str, str]:
    mcp_version = _read_pyproject_version(root)
    npm_version = _read_json_version(root / "fovux-mcp-npm" / "package.json")
    studio_version = _read_json_version(root / "fovux-studio" / "package.json")
    for version in (mcp_version, npm_version, studio_version):
        if not _VERSION_PATTERN.fullmatch(version):
            raise SystemExit(f"Invalid release version: {version}")
    if npm_version != mcp_version:
        raise SystemExit("The npm wrapper version must match the Python package version")
    return mcp_version, npm_version, studio_version


def _is_unpublished_candidate(root: Path, mcp_version: str) -> bool:
    """Return whether package metadata is ahead of the reviewed published baseline."""
    baseline_path = root / "release-baseline.json"
    if not baseline_path.exists():
        return True
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    published = baseline.get("published_release")
    if not isinstance(published, str) or not _VERSION_PATTERN.fullmatch(published):
        raise SystemExit("release-baseline.json has no valid published_release")
    return published != mcp_version


def _sync_server_json(mcp_root: Path, version: str) -> bool:
    path = mcp_root / "server.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    if data.get("version") != version:
        data["version"] = version
        changed = True
    packages = data.get("packages", [])
    for package in packages:
        if package.get("version") != version:
            package["version"] = version
            changed = True
    if changed:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Updated server.json to {version}")
    return changed


def _sync_root_mcp_json(root: Path, version: str) -> bool:
    path = root / "mcp.json"
    if not path.exists():
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    if data.get("version") != version:
        data["version"] = version
        changed = True
    for package in data.get("packages", []):
        if package.get("version") != version:
            package["version"] = version
            changed = True
    if changed:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(f"Updated mcp.json to {version}")
    return changed


def _sync_uv_lock(mcp_root: Path, version: str) -> bool:
    path = mcp_root / "uv.lock"
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    pattern = r'(?m)(\[\[package\]\]\nname = "fovux-mcp"\nversion = ")[^"]+(")'
    new_content, count = re.subn(pattern, rf"\g<1>{version}\2", content, count=1)
    if count == 0:
        raise SystemExit("Could not find fovux-mcp package version in uv.lock")
    if new_content != content:
        path.write_text(new_content, encoding="utf-8")
        print(f"Updated uv.lock to {version}")
        return True
    return False


def _sync_smithery_yaml(mcp_root: Path, version: str) -> bool:
    path = mcp_root / "smithery.yaml"
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    new_content = re.sub(
        r'^version:\s*"?[\d.]+"?',
        f'version: "{version}"',
        content,
        flags=re.MULTILINE,
    )
    if new_content != content:
        path.write_text(new_content, encoding="utf-8")
        print(f"Updated smithery.yaml to {version}")
        return True
    return False


def _extract_changelog_section(text: str, version: str, *, label: str) -> str:
    heading = re.search(rf"^##\s+\[{re.escape(version)}\][^\n]*\n", text, flags=re.MULTILINE)
    if heading is None:
        raise ValueError(f"{label} changelog is missing release {version}")
    next_heading = re.search(r"^##\s+\[", text[heading.end() :], flags=re.MULTILINE)
    end = heading.end() + next_heading.start() if next_heading else len(text)
    section = text[heading.end() : end].strip()
    if not section:
        raise ValueError(f"{label} changelog release {version} is empty")
    return re.sub(r"^(#{3,5}) ", r"#\1 ", section, flags=re.MULTILINE)


def render_candidate_release_notes(
    *,
    mcp_version: str,
    npm_version: str,
    studio_version: str,
    changelogs: Mapping[str, str],
) -> str:
    """Render deterministic notes for versions that are not published yet."""
    mcp_changes = _extract_changelog_section(changelogs["mcp"], mcp_version, label="fovux-mcp")
    npm_changes = _extract_changelog_section(changelogs["npm"], npm_version, label="fovux-mcp-npm")
    studio_changes = _extract_changelog_section(
        changelogs["studio"], studio_version, label="fovux-studio"
    )
    candidate_table = "\n".join(
        (
            "<!-- release-baseline:start -->",
            "| Component | Candidate version | Channel status | Evidence |",
            "| --- | --- | --- | --- |",
            (
                f"| Python package `fovux-mcp` | `{mcp_version}` | "
                "Pending publication | Generated after registry verification |"
            ),
            (
                f"| npm wrapper `fovux-mcp` | `{npm_version}` | "
                "Pending publication | Generated after registry verification |"
            ),
            (
                "| VS Code extension `oaslananka.fovuxstudiokit` | "
                f"`{studio_version}` | Pending publication | "
                "Generated after marketplace verification |"
            ),
            "<!-- release-baseline:end -->",
        )
    )
    return f"""# Fovux {mcp_version} Release Notes

Fovux {mcp_version} is the current release candidate for the local-first edge-AI computer vision
workbench. Package publication remains pending until the release workflow verifies every configured
registry and extension marketplace.

## Package Versions and Release Evidence

{candidate_table}

The final GitHub Release evidence will include:

- VSIX packaging status and publish results for VS Marketplace and Open VSX;
- SPDX SBOM files, checksums, and provenance attestations;
- registry verification evidence JSON and a smoke-test result for every published channel.

## Included Changes

### Python package `fovux-mcp` {mcp_version}

{mcp_changes}

### npm wrapper `fovux-mcp` {npm_version}

{npm_changes}

### Fovux Studio {studio_version}

{studio_changes}

## Upgrade Path

```bash
uv tool upgrade fovux-mcp
npm install -g fovux-mcp@latest
```

## Release Validation

- `python scripts/check_versions.py`
- `python scripts/check_docs_truth.py`
- `python scripts/check_release_truth.py`
- `node scripts/validate_release_automation.mjs`
- registry, VS Marketplace, and Open VSX verification in the release workflow
"""


def _sync_root_changelog(root: Path, version: str) -> bool:
    path = root / CHANGELOG_FILENAME
    if not path.exists():
        return False
    content = path.read_text(encoding="utf-8")
    match = re.search(r"^##\s*\[([^\]]+)\]", content, re.MULTILINE)
    if not match or match.group(1) == version:
        return False
    first_header = content.find("## [")
    if first_header < 0:
        return False
    new_section = (
        f"## [{version}] - {date.today().isoformat()}\n\n"
        "### Added\n\n"
        "- Synchronized release package updates.\n\n"
    )
    path.write_text(content[:first_header] + new_section + content[first_header:], encoding="utf-8")
    print(f"Updated root CHANGELOG.md to include version {version}")
    return True


def _sync_docs(root: Path, mcp_version: str, npm_version: str, studio_version: str) -> bool:
    changed = _sync_root_changelog(root, mcp_version)
    changelogs = {
        "mcp": (root / "fovux-mcp" / CHANGELOG_FILENAME).read_text(encoding="utf-8"),
        "npm": (root / "fovux-mcp-npm" / CHANGELOG_FILENAME).read_text(encoding="utf-8"),
        "studio": (root / "fovux-studio" / CHANGELOG_FILENAME).read_text(encoding="utf-8"),
    }
    rendered = render_candidate_release_notes(
        mcp_version=mcp_version,
        npm_version=npm_version,
        studio_version=studio_version,
        changelogs=changelogs,
    )
    targets = (
        root / "RELEASE_NOTES.md",
        root / "docs" / "release-notes" / f"{mcp_version}.md",
    )
    targets[1].parent.mkdir(parents=True, exist_ok=True)
    for path in targets:
        current = path.read_text(encoding="utf-8") if path.exists() else ""
        if current != rendered:
            path.write_text(rendered, encoding="utf-8")
            print(f"Updated {path.relative_to(root)} for release candidate {mcp_version}")
            changed = True
    return changed


def main() -> int:
    """Synchronize release metadata files and return a process status code."""
    root = _repo_root()
    mcp_version, npm_version, studio_version = _read_package_versions(root)
    mcp_root = root / "fovux-mcp"
    changes = (
        _sync_server_json(mcp_root, mcp_version),
        _sync_smithery_yaml(mcp_root, mcp_version),
        _sync_root_mcp_json(root, mcp_version),
        _sync_uv_lock(mcp_root, mcp_version),
        (
            _sync_docs(root, mcp_version, npm_version, studio_version)
            if _is_unpublished_candidate(root, mcp_version)
            else False
        ),
    )
    if not any(changes):
        print(f"Release candidate metadata already at {mcp_version}. No changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
