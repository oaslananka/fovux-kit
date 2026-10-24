"""Regression guard: frozen MCP dependency lock cannot roll back known security fixes."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import yaml  # type: ignore[import-untyped]

ROOT = Path(__file__).resolve().parents[3]
LOCK = ROOT / "fovux-mcp" / "uv.lock"

# Minimal public patched releases established by pip-audit and OSV on 2026-10-24.
MIN_PATCHED = {
    "certifi": (2026, 10, 19),
    "fastmcp": (3, 4, 10),
    "fastmcp-slim": (3, 4, 10),
    "mcp": (1, 30, 0),
    "opentelemetry-api": (1, 45, 1),
    "pillow": (13, 0, 0),
    "filelock": (4, 2, 1),
    "setuptools": (84, 1, 0),
    "virtualenv": (21, 14, 9),
}


def _require(condition: bool, detail: object) -> None:
    """Fail explicitly even under Python optimized execution (-O)."""
    if not condition:
        raise AssertionError(detail)


def test_frozen_lock_contains_patched_stable_versions() -> None:
    packages = tomllib.loads(LOCK.read_text(encoding="utf-8"))["package"]
    for name, minimum in MIN_PATCHED.items():
        versions = [pkg["version"] for pkg in packages if pkg["name"] == name]
        _require(len(versions) == 1, name)
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", versions[0])
        _require(match is not None, (name, versions))
        _require(tuple(map(int, match.groups())) >= minimum, (name, versions[0], minimum))


def test_studio_manifest_and_lock_contain_patched_vitest_and_vite() -> None:
    """Prevent a future Studio lock refresh from restoring known vulnerabilities."""
    studio = ROOT / "fovux-studio"
    manifest = json.loads((studio / "package.json").read_text(encoding="utf-8"))
    lock = yaml.safe_load((studio / "pnpm-lock.yaml").read_text(encoding="utf-8"))
    for section, name, minimum in (
        ("devDependencies", "vitest", (4, 1, 12)),
        ("devDependencies", "@vitest/coverage-v8", (4, 1, 12)),
        ("devDependencies", "vite", (8, 1, 6)),
        ("overrides", "vite", (8, 1, 6)),
    ):
        definition = (
            manifest[section] if section == "devDependencies" else manifest["pnpm"][section]
        )
        version = str(definition[name]).lstrip("^~")
        match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
        _require(match is not None and tuple(map(int, match.groups())) >= minimum, (name, version))
    resolved = lock["packages"]
    for name, minimum in (
        ("@vitest/mocker", (4, 1, 12)),
        ("@vitest/coverage-v8", (4, 1, 12)),
        ("vitest", (4, 1, 12)),
        ("vite", (8, 1, 6)),
    ):
        versions = []
        for key in resolved:
            match = re.fullmatch(re.escape(name) + r"@(\d+)\.(\d+)\.(\d+)", key)
            if match is not None:
                versions.append(tuple(map(int, match.groups())))
        _require(
            bool(versions) and all(version >= minimum for version in versions), (name, versions)
        )
