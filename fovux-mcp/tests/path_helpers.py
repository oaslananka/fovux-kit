"""Path helpers for tests that also run under mutmut's copied tree."""

from __future__ import annotations

from pathlib import Path


def _has_marker(root: Path, marker: tuple[str, ...]) -> bool:
    return root.joinpath(*marker).exists()


def _find_root(start: Path, markers: tuple[tuple[str, ...], ...], label: str) -> Path:
    for parent in (start, *start.parents):
        if all(_has_marker(parent, marker) for marker in markers):
            return parent
    raise RuntimeError(f"Could not locate {label} from start={start} with markers={markers}")


def find_package_root(start: Path) -> Path:
    return _find_root(
        start.resolve(),
        (
            ("pyproject.toml",),
            ("Dockerfile",),
            ("scripts", "check_tool_docs.py"),
            ("src", "fovux"),
        ),
        "fovux-mcp package root",
    )


def find_monorepo_root(start: Path) -> Path:
    return _find_root(
        start.resolve(),
        (("scripts", "check_versions.py"), ("fovux-mcp", "pyproject.toml")),
        "monorepo root",
    )
