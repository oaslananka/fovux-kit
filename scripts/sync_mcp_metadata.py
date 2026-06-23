"""Keep server.json and smithery.yaml versions in lockstep with pyproject.toml.

Run as:
    python scripts/sync_mcp_metadata.py

Idempotent — writes only when a version mismatch is detected.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_pyproject_version(root: Path) -> str:
    content = (root / "fovux-mcp" / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        raise SystemExit("Could not find version in pyproject.toml")
    return match.group(1)


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
    for pkg in packages:
        if pkg.get("version") != version:
            pkg["version"] = version
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
    for pkg in data.get("packages", []):
        if pkg.get("version") != version:
            pkg["version"] = version
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


def _sync_docs(root: Path, version: str) -> bool:
    changed = False

    # 1. Sync root CHANGELOG.md
    changelog_path = root / "CHANGELOG.md"
    if changelog_path.exists():
        content = changelog_path.read_text(encoding="utf-8")
        # Check if the topmost header is already for this version
        match = re.search(r"^##\s*\[([^\]]+)\]", content, re.MULTILINE)
        if match and match.group(1) != version:
            first_header_pos = content.find("## [")
            if first_header_pos != -1:
                from datetime import datetime

                today = datetime.now().strftime("%Y-%m-%d")
                new_section = (
                    f"## [{version}] - {today}\n\n"
                    "### Added\n\n"
                    "- Synchronized release package updates.\n\n"
                )
                new_content = (
                    content[:first_header_pos] + new_section + content[first_header_pos:]
                )
                changelog_path.write_text(new_content, encoding="utf-8")
                print(f"Updated root CHANGELOG.md to include version {version}")
                changed = True

    # 2. Sync root RELEASE_NOTES.md
    rn_path = root / "RELEASE_NOTES.md"
    if rn_path.exists():
        content = rn_path.read_text(encoding="utf-8")
        new_content = re.sub(
            r"^#\s+Fovux\s+[^\s]+\s+Release\s+Notes",
            f"# Fovux {version} Release Notes",
            content,
            flags=re.MULTILINE,
        )
        if new_content != content:
            rn_path.write_text(new_content, encoding="utf-8")
            print(f"Updated root RELEASE_NOTES.md version to {version}")
            changed = True

    # 3. Create docs/release-notes/<version>.md if not exists
    docs_rn_path = root / "docs" / "release-notes" / f"{version}.md"
    if not docs_rn_path.exists():
        if rn_path.exists():
            rn_content = rn_path.read_text(encoding="utf-8")
            docs_rn_path.write_text(rn_content, encoding="utf-8")
            print(f"Created docs/release-notes/{version}.md stub")
            changed = True

    return changed


def main() -> int:
    """Synchronize release metadata files and return a process status code."""
    root = _repo_root()
    version = _read_pyproject_version(root)
    mcp_root = root / "fovux-mcp"
    s1 = _sync_server_json(mcp_root, version)
    s2 = _sync_smithery_yaml(mcp_root, version)
    s3 = _sync_root_mcp_json(root, version)
    s4 = _sync_uv_lock(mcp_root, version)
    s5 = _sync_docs(root, version)
    if not s1 and not s2 and not s3 and not s4 and not s5:
        print(f"MCP metadata already at {version}. No changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
