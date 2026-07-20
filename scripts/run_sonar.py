"""Run an explicit local SonarQube Cloud branch or pull-request analysis."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from scanner_runner import run_scanner

REPO_ROOT = Path(__file__).resolve().parent.parent
_BRANCH_PATTERN = re.compile(r"^[A-Za-z0-9._/-]+$")


def build_parser() -> argparse.ArgumentParser:
    """Build the Sonar wrapper argument parser."""
    parser = argparse.ArgumentParser(description="Run local SonarScanner safely.")
    parser.add_argument(
        "--branch", help="Analysis branch name; defaults to the current git branch."
    )
    parser.add_argument("--pull-request", type=int, help="Pull request number.")
    parser.add_argument("--base", help="Pull request base branch.")
    parser.add_argument(
        "--required",
        action="store_true",
        help="Fail when sonar-scanner or SONAR_TOKEN is not configured.",
    )
    return parser


def _validate_branch(parser: argparse.ArgumentParser, value: str, option: str) -> None:
    if not _BRANCH_PATTERN.fullmatch(value):
        parser.error(f"{option} contains unsupported characters")


def detect_current_branch(parser: argparse.ArgumentParser) -> str:
    """Return the current non-detached git branch name."""
    git_executable = shutil.which("git")
    if git_executable is None:
        parser.error("git executable is required to detect the current branch")
    result = subprocess.run(  # noqa: S603
        [git_executable, "branch", "--show-current"],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    branch = result.stdout.strip()
    if result.returncode != 0 or not branch:
        parser.error("--branch is required when git is in detached HEAD state")
    return branch


def build_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[str]:
    """Build SonarScanner arguments without putting credentials on the command line."""
    branch = args.branch or detect_current_branch(parser)
    _validate_branch(parser, branch, "--branch")
    if args.pull_request is None:
        if args.base is not None:
            parser.error("--base requires --pull-request")
        return ["sonar-scanner", f"-Dsonar.branch.name={branch}"]

    if not args.base:
        parser.error("--pull-request requires --base")
    _validate_branch(parser, args.base, "--base")
    return [
        "sonar-scanner",
        f"-Dsonar.pullrequest.key={args.pull_request}",
        f"-Dsonar.pullrequest.branch={branch}",
        f"-Dsonar.pullrequest.base={args.base}",
    ]


def main(argv: Sequence[str] | None = None) -> int:
    """Run one authenticated SonarScanner analysis."""
    parser = build_parser()
    args = parser.parse_args(argv)
    command = build_command(args, parser)
    return run_scanner(
        name="SonarQube Cloud",
        command=command,
        token_names=("SONAR_TOKEN",),
        required=args.required,
        environ=dict(os.environ),
        cwd=REPO_ROOT,
    )


if __name__ == "__main__":
    raise SystemExit(main())
