"""Run the credential-free repository OSV-Scanner dependency scan safely."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from scanner_runner import run_scanner

REPO_ROOT = Path(__file__).resolve().parent.parent
OSV_COMMAND = (
    "osv-scanner",
    "scan",
    "source",
    "--lockfile=fovux-mcp/uv.lock",
    "--lockfile=fovux-studio/pnpm-lock.yaml",
    "--lockfile=fovux-mcp-npm/package-lock.json",
    ".",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the OSV-Scanner wrapper argument parser."""
    parser = argparse.ArgumentParser(description="Run the repository OSV dependency scan.")
    parser.add_argument(
        "--required",
        action="store_true",
        help="Fail when the OSV-Scanner executable is not installed.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Scan all tracked package-manager lockfiles without credentials."""
    args = build_parser().parse_args(argv)
    return run_scanner(
        name="OSV-Scanner",
        command=OSV_COMMAND,
        token_names=(),
        required=args.required,
        cwd=REPO_ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())
