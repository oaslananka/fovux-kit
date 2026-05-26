"""Check release-controlled version coherence across the Fovux monorepo."""

from __future__ import annotations

import json
import re
from pathlib import Path


def _repo_root() -> Path:
    """Locate the monorepo root relative to this script."""
    return Path(__file__).resolve().parent.parent


def _read_pyproject_version(root: Path) -> str:
    """Extract version from pyproject.toml."""
    pyproject = root / "fovux-mcp" / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        return "<not found in pyproject.toml>"
    return match.group(1)


def _read_init_version(root: Path) -> str:
    """Extract __version__ from fovux/__init__.py."""
    init_file = root / "fovux-mcp" / "src" / "fovux" / "__init__.py"
    content = init_file.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', content, re.MULTILINE)
    if not match:
        return "<not found in __init__.py>"
    return match.group(1)


def _read_package_json_version(root: Path) -> str:
    """Extract version from fovux-studio/package.json."""
    pkg = root / "fovux-studio" / "package.json"
    data = json.loads(pkg.read_text(encoding="utf-8"))
    return str(data.get("version", "<not found in package.json>"))


def _read_jsonpath_version(path: Path, *keys: str | int) -> str:
    """Extract a nested version value from a JSON metadata file."""
    if not path.exists():
        return f"<{path.name} not found>"
    value: object = json.loads(path.read_text(encoding="utf-8"))
    for key in keys:
        try:
            if isinstance(key, int) and isinstance(value, list):
                value = value[key]
            elif isinstance(key, str) and isinstance(value, dict):
                value = value[key]
            else:
                return f"<missing {'.'.join(map(str, keys))} in {path.name}>"
        except (IndexError, KeyError):
            return f"<missing {'.'.join(map(str, keys))} in {path.name}>"
    return str(value)


def _read_changelog_top_version(changelog_path: Path) -> str:
    """Extract the version from the topmost ## [x.y.z] header."""
    if not changelog_path.exists():
        return f"<{changelog_path.name} not found>"
    content = changelog_path.read_text(encoding="utf-8")
    match = re.search(r"^##\s*\[([^\]]+)\]", content, re.MULTILINE)
    if not match:
        return f"<no version header in {changelog_path.name}>"
    version = match.group(1)
    if version.lower() == "unreleased":
        # Look for the next versioned header
        matches = re.findall(r"^##\s*\[([^\]]+)\]", content, re.MULTILINE)
        for candidate in matches:
            if candidate.lower() != "unreleased":
                return candidate
        return "Unreleased"
    return version


def _read_smithery_version(root: Path) -> str:
    """Extract version from fovux-mcp/smithery.yaml."""
    smithery = root / "fovux-mcp" / "smithery.yaml"
    if not smithery.exists():
        return "<smithery.yaml not found>"
    content = smithery.read_text(encoding="utf-8")
    match = re.search(r'^version:\s*"?([^"\s]+)"?', content, re.MULTILINE)
    if not match:
        return "<no version in smithery.yaml>"
    return match.group(1)


def _read_uv_lock_version(root: Path) -> str:
    """Extract the editable fovux-mcp package version from uv.lock."""
    lockfile = root / "fovux-mcp" / "uv.lock"
    if not lockfile.exists():
        return "<uv.lock not found>"
    content = lockfile.read_text(encoding="utf-8")
    match = re.search(
        r'(?m)^\[\[package\]\]\nname = "fovux-mcp"\nversion = "([^"]+)"',
        content,
    )
    if not match:
        return "<fovux-mcp version not found in uv.lock>"
    return match.group(1)


def check_versions() -> int:
    """Check all version sources and return 0 if coherent, 1 otherwise."""
    root = _repo_root()

    sources: dict[str, str] = {
        "fovux-mcp/pyproject.toml": _read_pyproject_version(root),
        "fovux-mcp/uv.lock": _read_uv_lock_version(root),
        "fovux-mcp/src/fovux/__init__.py": _read_init_version(root),
        "fovux-mcp/server.json": _read_jsonpath_version(
            root / "fovux-mcp" / "server.json", "version"
        ),
        "fovux-mcp/server.json packages[0]": _read_jsonpath_version(
            root / "fovux-mcp" / "server.json", "packages", 0, "version"
        ),
        "fovux-mcp/smithery.yaml": _read_smithery_version(root),
        "mcp.json": _read_jsonpath_version(root / "mcp.json", "version"),
        "mcp.json packages[0]": _read_jsonpath_version(root / "mcp.json", "packages", 0, "version"),
        "fovux-studio/package.json": _read_package_json_version(root),
        "fovux-mcp/CHANGELOG.md": _read_changelog_top_version(root / "fovux-mcp" / "CHANGELOG.md"),
        "fovux-studio/CHANGELOG.md": _read_changelog_top_version(
            root / "fovux-studio" / "CHANGELOG.md"
        ),
    }

    unique_versions = set(sources.values())

    if len(unique_versions) == 1:
        version = unique_versions.pop()
        print(f"All version sources are coherent: {version}")
        return 0

    print("VERSION MISMATCH DETECTED")
    print()
    max_label = max(len(label) for label in sources)
    for label, version in sources.items():
        most_common = max(unique_versions, key=lambda v: list(sources.values()).count(v))
        marker = "  " if version == most_common else "!!"
        print(f"  {marker} {label:<{max_label}}  {version}")
    print()
    print(f"Found {len(unique_versions)} distinct versions: {sorted(unique_versions)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(check_versions())
