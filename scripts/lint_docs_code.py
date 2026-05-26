"""Syntax-check fenced Python and Bash snippets in documentation."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

FENCE_RE = re.compile(r"```(?P<lang>python|bash|sh)\n(?P<body>.*?)```", re.DOTALL)
SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "build",
    "dist",
    "htmlcov",
    "node_modules",
    "out",
    "site",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, help="Documentation root to scan.")
    args = parser.parse_args()
    failures: list[str] = []

    root = args.root.resolve()
    for doc_path in sorted(root.rglob("*.md")):
        if SKIP_PARTS.intersection(doc_path.relative_to(root).parts):
            continue
        text = doc_path.read_text(encoding="utf-8")
        for index, match in enumerate(FENCE_RE.finditer(text), start=1):
            lang = match.group("lang")
            body = match.group("body")
            if lang == "python":
                failures.extend(_check_python(doc_path, index, body))
            else:
                failures.extend(_check_bash(doc_path, index, body))

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    return 0


def _check_python(doc_path: Path, index: int, body: str) -> list[str]:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(body)
        temp_path = Path(handle.name)
    try:
        result = subprocess.run(  # noqa: S603 - fixed executable and temp file path
            [sys.executable, "-m", "py_compile", str(temp_path)],
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        temp_path.unlink(missing_ok=True)
    if result.returncode == 0:
        return []
    return [f"{doc_path}:{index}: python snippet failed syntax check\n{result.stderr}"]


def _check_bash(doc_path: Path, index: int, body: str) -> list[str]:
    result = subprocess.run(  # noqa: S603 - fixed executable, syntax-only stdin check
        ["bash", "-n"],
        input=body,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return []
    return [f"{doc_path}:{index}: bash snippet failed syntax check\n{result.stderr}"]


if __name__ == "__main__":
    raise SystemExit(main())
