"""Run the pinned credential-free Gitleaks repository scan safely."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from scanner_runner import run_scanner, verify_scanner_version

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_GITLEAKS_VERSION = "8.30.1"
GITLEAKS_COMMAND = ("gitleaks", "detect", "--no-banner", "--redact")


def build_parser() -> argparse.ArgumentParser:
    """Build the Gitleaks wrapper argument parser."""
    parser = argparse.ArgumentParser(description="Run the repository Gitleaks scan.")
    parser.add_argument(
        "--required",
        action="store_true",
        help="Fail when the pinned Gitleaks executable is unavailable.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Scan repository history and content using the CI-equivalent Gitleaks pin."""
    args = build_parser().parse_args(argv)
    version_result = verify_scanner_version(
        name="Gitleaks",
        executable="gitleaks",
        version_args=("version",),
        expected_version=EXPECTED_GITLEAKS_VERSION,
        version_pattern=r"^v?([0-9]+\.[0-9]+\.[0-9]+)\s*$",
        required=args.required,
    )
    if version_result is not None:
        return version_result
    return run_scanner(
        name="Gitleaks secret scan",
        command=GITLEAKS_COMMAND,
        token_names=(),
        required=args.required,
        cwd=REPO_ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())
