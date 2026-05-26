"""Pre-commit hook that rejects staging of build artifacts.

Returns non-zero if any staged path matches a known generated-file pattern.
"""

from __future__ import annotations

import sys
from pathlib import PurePosixPath

_FORBIDDEN_PATTERNS: list[str] = [
    "fovux-mcp/htmlcov/",
    "fovux-mcp/coverage.xml",
    "fovux-mcp/junit.xml",
    "fovux-mcp/.coverage",
    "fovux-mcp/requirements-audit.txt",
    "fovux-mcp/requirements-build.txt",
    "fovux-mcp/sbom.cdx.json",
    "fovux-mcp/sbom.spdx",
    "fovux-mcp/dist/",
    "fovux-mcp/build/",
    "fovux-mcp/site/",
    "fovux-studio/out/",
    "fovux-studio/coverage/",
    "fovux-studio/.vscode-test/",
]

_FORBIDDEN_SUFFIXES: list[str] = [
    ".vsix",
    ".pyc",
]

_FORBIDDEN_DIRS: list[str] = [
    "__pycache__",
]


def _is_forbidden(path_str: str) -> bool:
    """Check whether a staged path matches any forbidden pattern."""
    posix = PurePosixPath(path_str.replace("\\", "/"))

    for pattern in _FORBIDDEN_PATTERNS:
        if pattern.endswith("/"):
            if str(posix).startswith(pattern) or f"/{pattern}" in str(posix):
                return True
        elif str(posix) == pattern or str(posix).endswith(f"/{pattern}"):
            return True

    for suffix in _FORBIDDEN_SUFFIXES:
        if posix.suffix == suffix:
            return True

    for dirname in _FORBIDDEN_DIRS:
        if dirname in posix.parts:
            return True

    return False


def main() -> int:
    """Check staged files for forbidden build artifacts."""
    violations: list[str] = []
    for path_arg in sys.argv[1:]:
        if _is_forbidden(path_arg):
            violations.append(path_arg)

    if violations:
        print("ERROR: Build artifacts must not be committed:")
        for violation in violations:
            print(f"  - {violation}")
        print("\nRemove them with: git rm --cached <path>")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
