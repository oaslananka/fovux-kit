from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MCP_DIR = ROOT / "fovux-mcp"
STUDIO_DIR = ROOT / "fovux-studio"
PNPM = "pnpm.cmd" if os.name == "nt" else "pnpm"

PRETTIER_EXTENSIONS = {
    ".cjs",
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsonc",
    ".jsx",
    ".md",
    ".mjs",
    ".scss",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
ESLINT_EXTENSIONS = {".cjs", ".js", ".jsx", ".mjs", ".ts", ".tsx"}


def _run(command: list[str], cwd: Path = ROOT) -> None:
    """Run a command and fail with a friendly message when tooling is missing."""
    print(f"> {' '.join(command)}")
    try:
        subprocess.run(command, cwd=cwd, check=True)
    except FileNotFoundError as exc:
        tool = command[0]
        raise SystemExit(
            f"Missing required tool: {tool}. Install the repo toolchain first "
            "(uv for fovux-mcp, Corepack/pnpm for fovux-studio)."
        ) from exc


def _existing_repo_paths(raw_paths: list[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in raw_paths:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = (ROOT / candidate).resolve()
        else:
            candidate = candidate.resolve()
        if not candidate.exists() or candidate.is_dir():
            continue
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            continue
        paths.append(candidate)
    return paths


def _root_relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _studio_absolute(paths: list[Path], extensions: set[str]) -> list[str]:
    selected: list[str] = []
    for path in paths:
        if path.suffix.lower() not in extensions:
            continue
        try:
            relative = path.relative_to(STUDIO_DIR)
        except ValueError:
            continue
        if relative.parts[0] not in {"src", "test"}:
            continue
        selected.append(str(path))
    return selected


def run_pre_commit(file_args: list[str]) -> None:
    """Run fast staged checks for the current commit."""
    paths = _existing_repo_paths(file_args)
    python_files = [
        _root_relative(path)
        for path in paths
        if path.suffix == ".py" and MCP_DIR in path.parents
    ]
    prettier_files = [str(path) for path in paths if path.suffix.lower() in PRETTIER_EXTENSIONS]
    eslint_files = _studio_absolute(paths, ESLINT_EXTENSIONS)

    if python_files:
        _run(["uv", "run", "--project", "fovux-mcp", "ruff", "check", "--fix", *python_files])
        _run(["uv", "run", "--project", "fovux-mcp", "ruff", "format", *python_files])

    if prettier_files:
        _run([PNPM, "--dir", str(STUDIO_DIR), "exec", "prettier", "--write", *prettier_files])

    if eslint_files:
        _run(
            [
                PNPM,
                "--dir",
                str(STUDIO_DIR),
                "exec",
                "eslint",
                "--fix",
                "--no-error-on-unmatched-pattern",
                *eslint_files,
            ]
        )


def check_versions() -> None:
    """Enforce version coherence across the monorepo."""
    _run([sys.executable, str(ROOT / "scripts" / "check_versions.py")])


def mcp_check() -> None:
    """Run the locked backend validation used locally and in CI."""
    check_versions()
    mcp_lint()
    _run(["uv", "run", "pytest", "tests", "--no-header", "-q"], cwd=MCP_DIR)
    mcp_security()


def mcp_lint() -> None:
    """Run the backend lint and type-check gate."""
    _run(["uv", "lock", "--check"], cwd=MCP_DIR)
    _run(["uv", "run", "ruff", "check", "src", "tests"], cwd=MCP_DIR)
    _run(["uv", "run", "ruff", "format", "--check", "src", "tests"], cwd=MCP_DIR)
    _run(["uv", "run", "mypy", "--strict", "--warn-unused-ignores", "src/fovux"], cwd=MCP_DIR)


def mcp_security() -> None:
    """Run backend static and dependency security checks."""
    _run(["uv", "run", "bandit", "-r", "src/fovux", "-ll"], cwd=MCP_DIR)
    mcp_audit()


def mcp_docs() -> None:
    """Build the backend docs and lint embedded code blocks."""
    _run(["uv", "run", "mkdocs", "build", "--strict"], cwd=MCP_DIR)
    _run(["uv", "run", "python", "../scripts/lint_docs_code.py", "docs"], cwd=MCP_DIR)


def mcp_audit() -> None:
    """Export runtime requirements from the lockfile and audit them."""
    _run(["uv", "lock", "--check"], cwd=MCP_DIR)
    _run(
        [
            "uv",
            "export",
            "--no-dev",
            "--no-editable",
            "--no-emit-project",
            "--no-hashes",
            "--output-file",
            "requirements-audit.txt",
        ],
        cwd=MCP_DIR,
    )
    _run(["uvx", "pip-audit", "-r", "requirements-audit.txt"], cwd=MCP_DIR)


def mcp_build() -> None:
    """Build the backend package to catch packaging regressions locally."""
    _run(["uv", "lock", "--check"], cwd=MCP_DIR)
    _run(["uv", "run", "python", "-m", "build"], cwd=MCP_DIR)


def studio_check() -> None:
    """Run the main Studio quality gates."""
    _run([PNPM, "check"], cwd=STUDIO_DIR)


def studio_verify() -> None:
    """Run the full Studio validation used in CI."""
    _run([PNPM, "verify"], cwd=STUDIO_DIR)


def repo_check() -> None:
    """Run the shared local quality gate before pushing."""
    check_versions()
    mcp_check()
    studio_check()


def repo_verify() -> None:
    """Run the fuller local validation that matches the important CI gates."""
    check_versions()
    repo_check()
    mcp_docs()
    mcp_audit()
    mcp_build()
    studio_verify()


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for local quality gate modes."""
    parser = argparse.ArgumentParser(description="Local quality gates for the Fovux monorepo.")
    parser.add_argument(
        "mode",
        choices=[
            "pre-commit",
            "pre-push",
            "mcp-lint",
            "mcp-check",
            "mcp-docs",
            "mcp-audit",
            "mcp-build",
            "mcp-security",
            "studio-check",
            "studio-verify",
            "repo-check",
            "repo-verify",
        ],
    )
    parser.add_argument("paths", nargs="*")
    return parser


def main() -> int:
    """Dispatch the requested quality gate mode."""
    args = build_parser().parse_args()

    os.chdir(ROOT)

    if args.mode == "pre-commit":
        run_pre_commit(args.paths)
    elif args.mode == "pre-push":
        repo_check()
    elif args.mode == "mcp-lint":
        mcp_lint()
    elif args.mode == "mcp-check":
        mcp_check()
    elif args.mode == "mcp-docs":
        mcp_docs()
    elif args.mode == "mcp-audit":
        mcp_audit()
    elif args.mode == "mcp-build":
        mcp_build()
    elif args.mode == "mcp-security":
        mcp_security()
    elif args.mode == "studio-check":
        studio_check()
    elif args.mode == "studio-verify":
        studio_verify()
    elif args.mode == "repo-check":
        repo_check()
    elif args.mode == "repo-verify":
        repo_verify()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
