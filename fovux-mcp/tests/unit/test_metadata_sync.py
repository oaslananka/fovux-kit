"""Tests for MCP metadata version synchronization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.path_helpers import find_monorepo_root

REPO_ROOT = find_monorepo_root(Path(__file__))


def _read_pyproject_version() -> str:
    import re

    content = (REPO_ROOT / "fovux-mcp" / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', content, re.MULTILINE)
    assert match, "Could not find version in pyproject.toml"
    return match.group(1)


def test_server_json_version_matches_pyproject() -> None:
    version = _read_pyproject_version()
    server_json = REPO_ROOT / "fovux-mcp" / "server.json"
    if not server_json.exists():
        pytest.skip("server.json not found")
    data = json.loads(server_json.read_text(encoding="utf-8"))
    assert data["version"] == version, f"server.json version {data['version']} != {version}"


def test_server_json_package_version_matches() -> None:
    version = _read_pyproject_version()
    server_json = REPO_ROOT / "fovux-mcp" / "server.json"
    if not server_json.exists():
        pytest.skip("server.json not found")
    data = json.loads(server_json.read_text(encoding="utf-8"))
    for pkg in data.get("packages", []):
        assert pkg["version"] == version, f"Package version {pkg['version']} != {version}"


def test_smithery_yaml_version_matches_pyproject() -> None:
    import re

    version = _read_pyproject_version()
    smithery = REPO_ROOT / "fovux-mcp" / "smithery.yaml"
    if not smithery.exists():
        pytest.skip("smithery.yaml not found")
    content = smithery.read_text(encoding="utf-8")
    match = re.search(r'^version:\s*"?([^"\s]+)"?', content, re.MULTILINE)
    assert match, "Could not find version in smithery.yaml"
    assert match.group(1) == version, f"smithery.yaml version {match.group(1)} != {version}"
