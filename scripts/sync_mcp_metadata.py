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


def main() -> int:
    """Synchronize release metadata files and return a process status code."""
    root = _repo_root()
    version = _read_pyproject_version(root)
    mcp_root = root / "fovux-mcp"
    s1 = _sync_server_json(mcp_root, version)
    s2 = _sync_smithery_yaml(mcp_root, version)
    s3 = _sync_root_mcp_json(root, version)
    s4 = _sync_uv_lock(mcp_root, version)
    if not s1 and not s2 and not s3 and not s4:
        print(f"MCP metadata already at {version}. No changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
