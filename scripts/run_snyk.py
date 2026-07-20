"""Run optional local Snyk Open Source and Snyk Code scans safely."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from scanner_runner import run_scanner

REPO_ROOT = Path(__file__).resolve().parent.parent
SNYK_COMMANDS = (
    ("snyk", "test", "--all-projects", "--severity-threshold=high"),
    ("snyk", "code", "test", "--severity-threshold=high"),
)


def build_parser() -> argparse.ArgumentParser:
    """Build the Snyk wrapper argument parser."""
    parser = argparse.ArgumentParser(description="Run local Snyk security scans.")
    parser.add_argument(
        "--required",
        action="store_true",
        help="Fail when the Snyk CLI or SNYK_TOKEN is not configured.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run Snyk Open Source followed by Snyk Code."""
    args = build_parser().parse_args(argv)
    environment = dict(os.environ)
    for index, command in enumerate(SNYK_COMMANDS, start=1):
        scan_name = "Snyk Open Source" if index == 1 else "Snyk Code"
        result = run_scanner(
            name=scan_name,
            command=command,
            token_names=("SNYK_TOKEN",),
            required=args.required,
            environ=environment,
            cwd=REPO_ROOT,
        )
        if result != 0:
            return result
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
