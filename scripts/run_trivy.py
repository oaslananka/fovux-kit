"""Run the credential-free Trivy filesystem vulnerability scan safely."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from scanner_runner import run_scanner, verify_scanner_version

REPO_ROOT = Path(__file__).resolve().parent.parent
EXPECTED_TRIVY_VERSION = "0.70.0"
TRIVY_COMMAND = (
    "trivy",
    "fs",
    "--scanners=vuln",
    "--severity=CRITICAL,HIGH",
    "--ignore-unfixed",
    "--exit-code=1",
    ".",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the Trivy wrapper argument parser."""
    parser = argparse.ArgumentParser(
        description="Run the repository Trivy filesystem scan."
    )
    parser.add_argument(
        "--required",
        action="store_true",
        help="Fail when the Trivy executable is not installed.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Scan repository dependencies using the same severity policy as CI."""
    args = build_parser().parse_args(argv)
    version_result = verify_scanner_version(
        name="Trivy",
        executable="trivy",
        version_args=("--version",),
        expected_version=EXPECTED_TRIVY_VERSION,
        version_pattern=r"^Version:\s+([^\s]+)",
        required=args.required,
    )
    if version_result is not None:
        return version_result
    return run_scanner(
        name="Trivy filesystem scan",
        command=TRIVY_COMMAND,
        token_names=(),
        required=args.required,
        cwd=REPO_ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())
