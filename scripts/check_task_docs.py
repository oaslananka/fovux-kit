"""Verify documented `task ...` commands exist in Taskfile.yml."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKFILE = ROOT / "Taskfile.yml"
DOC_PATHS = [
    ROOT / "README.md",
    ROOT / "CONTRIBUTING.md",
    ROOT / "docs",
    ROOT / "fovux-mcp" / "README.md",
]
TASK_REF_RE = re.compile(r"(?<![A-Za-z0-9_-])task\s+([A-Za-z0-9:_-]+)")
TASK_DEF_RE = re.compile(r"^  ([A-Za-z0-9:_-]+):\s*$", re.MULTILINE)


def _task_names() -> set[str]:
    """Read task names from the root Taskfile without requiring Task itself."""
    return set(TASK_DEF_RE.findall(TASKFILE.read_text(encoding="utf-8")))


def _markdown_files(path: Path) -> list[Path]:
    """Return Markdown files under a file or directory path."""
    if path.is_file():
        return [path]
    if not path.exists():
        return []
    return sorted(path.rglob("*.md"))


def _documented_task_refs() -> list[tuple[Path, int, str]]:
    """Return documented task command references with file and line."""
    refs: list[tuple[Path, int, str]] = []
    seen_files: set[Path] = set()
    for root in DOC_PATHS:
        for path in _markdown_files(root):
            if path in seen_files:
                continue
            seen_files.add(path)
            in_fence = False
            for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("```"):
                    in_fence = not in_fence
                    continue
                if in_fence:
                    match = re.match(r"^\s*task\s+([A-Za-z0-9:_-]+)(?:\s|$)", line)
                    if match:
                        refs.append((path, line_no, match.group(1)))
                for inline in re.findall(r"`task\s+([A-Za-z0-9:_-]+)`", line):
                    refs.append((path, line_no, inline))
    return refs


def main() -> int:
    """Run the documented task reference check."""
    tasks = _task_names()
    refs = _documented_task_refs()
    failures = [
        (path, line_no, name)
        for path, line_no, name in refs
        if name not in tasks and name != "command"
    ]

    if failures:
        for path, line_no, name in failures:
            rel = path.relative_to(ROOT)
            print(
                f"ERROR: {rel}:{line_no} documents `task {name}`, "
                f"but Taskfile.yml has no `{name}` task."
            )
        print("Regenerate/check with: `python scripts/check_task_docs.py`.")
        return 1

    print(f"Task docs check passed: {len(refs)} documented task references, {len(tasks)} tasks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
