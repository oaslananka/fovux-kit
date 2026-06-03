"""Run Prettier through the Fovux Studio package-manager pin."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path


DEFAULT_CHUNK_SIZE = 80
WINDOWS_CHUNK_SIZE = 5
PNPM_VERSION = "10.34.1"


def _chunks(values: list[str], size: int) -> Iterable[list[str]]:
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _prettier_chunk_size() -> int:
    if os.name == "nt":
        return WINDOWS_CHUNK_SIZE
    return DEFAULT_CHUNK_SIZE


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    studio_root = repo_root / "fovux-studio"
    files = [
        str((repo_root / file_name).resolve())
        for file_name in sys.argv[1:]
        if (repo_root / file_name).exists()
    ]
    if not files:
        return 0

    corepack = "corepack.cmd" if os.name == "nt" else "corepack"
    chunk_size = _prettier_chunk_size()
    for file_chunk in _chunks(files, chunk_size):
        result = subprocess.run(
            [
                corepack,
                f"pnpm@{PNPM_VERSION}",
                "--dir",
                str(studio_root),
                "--ignore-workspace",
                "exec",
                "prettier",
                "--write",
                *file_chunk,
            ],
            cwd=repo_root,
            check=False,
        )
        if result.returncode != 0:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
