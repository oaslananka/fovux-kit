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


def _read_npm_wrapper_package_version(root: Path) -> str:
    """Extract version from fovux-mcp-npm/package.json."""
    pkg = root / "fovux-mcp-npm" / "package.json"
    if not pkg.exists():
        return "<fovux-mcp-npm/package.json not found>"
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


def _read_title_version(path: Path) -> str:
    """Extract version from a markdown file's title header."""
    if not path.exists():
        return f"<{path.name} not found>"
    content = path.read_text(encoding="utf-8")
    match = re.search(r"^#\s+Fovux\s+([^\s]+)\s+Release", content, re.MULTILINE)
    if not match:
        return f"<no version title in {path.name}>"
    return match.group(1)


def _version_sources(root: Path) -> dict[str, dict[str, str]]:
    """Build version source groups by independently versioned artifact."""
    return {
        "MCP": {
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
            "mcp.json packages[0]": _read_jsonpath_version(
                root / "mcp.json", "packages", 0, "version"
            ),
            "fovux-mcp/CHANGELOG.md": _read_changelog_top_version(
                root / "fovux-mcp" / "CHANGELOG.md"
            ),
            "fovux-mcp-npm/package.json": _read_npm_wrapper_package_version(root),
            "fovux-mcp-npm/CHANGELOG.md": _read_changelog_top_version(
                root / "fovux-mcp-npm" / "CHANGELOG.md"
            ),
        },
        "Studio": {
            "fovux-studio/package.json": _read_package_json_version(root),
            "fovux-studio/CHANGELOG.md": _read_changelog_top_version(
                root / "fovux-studio" / "CHANGELOG.md"
            ),
        },
        "Docs": {
            "CHANGELOG.md (root)": _read_changelog_top_version(root / "CHANGELOG.md"),
            "RELEASE_NOTES.md": _read_title_version(root / "RELEASE_NOTES.md"),
            **{
                f"docs/release-notes/{p.name}": _read_title_version(p)
                for p in sorted((root / "docs" / "release-notes").glob("*.md"))
            }
        },
    }


def _print_group_mismatch(group_name: str, sources: dict[str, str]) -> None:
    """Print the mismatched versions for one release track."""
    unique_versions = set(sources.values())
    source_versions = list(sources.values())
    most_common = max(unique_versions, key=source_versions.count)
    max_label = max(len(label) for label in sources)

    print(f"{group_name} version sources:")
    for label, version in sources.items():
        marker = "  " if version == most_common else "!!"
        print(f"  {marker} {label:<{max_label}}  {version}")
    print(
        f"  Found {len(unique_versions)} distinct versions: {sorted(unique_versions)}"
    )


def _check_group(group_name: str, sources: dict[str, str]) -> bool:
    """Return true when one release track has exactly one version."""
    unique_versions = set(sources.values())
    if len(unique_versions) == 1:
        print(
            f"{group_name} version sources are coherent: {next(iter(unique_versions))}"
        )
        return True

    _print_group_mismatch(group_name, sources)
    return False


def _check_docs_group(sources: dict[str, str]) -> bool:
    """Check docs version surfaces against manifest versions."""
    manifest_version = _read_pyproject_version(_repo_root())
    ok = True

    # Root CHANGELOG top version must match the current package version.
    changelog_v = sources.get("CHANGELOG.md (root)", "")
    if changelog_v != manifest_version:
        print(f"  !! CHANGELOG.md (root) top version is {changelog_v}, expected {manifest_version}")
        ok = False

    # RELEASE_NOTES.md must match the current package version.
    rn_v = sources.get("RELEASE_NOTES.md", "")
    if rn_v != manifest_version:
        print(f"  !! RELEASE_NOTES.md version is {rn_v}, expected {manifest_version}")
        ok = False

    # Each docs/release-notes/<version>.md must have a matching title version.
    for key, version in sources.items():
        if not key.startswith("docs/release-notes/"):
            continue
        expected = key.removeprefix("docs/release-notes/").removesuffix(".md")
        fn_match = re.match(r"^\d+\.\d+\.\d+$", expected)
        if not fn_match:
            print(f"  !! {key}: unexpected filename pattern")
            ok = False
            continue
        if version != expected:
            print(f"  !! {key}: title version is {version}, expected {expected} (filename)")
            ok = False

    if ok:
        print(f"Docs version sources are coherent: {manifest_version}")
    return ok


def check_versions() -> int:
    """Check version source groups and return 0 if all are coherent."""
    root = _repo_root()
    groups = _version_sources(root)

    # Standard groups use internal consistency check.
    failed_groups = []
    for group_name, sources in groups.items():
        if group_name == "Docs":
            if not _check_docs_group(sources):
                failed_groups.append(group_name)
        elif not _check_group(group_name, sources):
            failed_groups.append(group_name)

    if not failed_groups:
        return 0

    print()
    print(f"VERSION MISMATCH DETECTED: {', '.join(failed_groups)}")
    return 1


if __name__ == "__main__":
    raise SystemExit(check_versions())
