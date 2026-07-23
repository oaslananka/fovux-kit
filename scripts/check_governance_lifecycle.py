"""Validate governance lifecycle, ADR, contributor, and review-policy docs."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    """Run repository governance-document and automation checks."""
    failures: list[str] = []
    lifecycle = _read(ROOT / "docs" / "issue-lifecycle.md")
    for phrase in [
        "Triage",
        "Ready",
        "In progress",
        "Waiting review",
        "Done/closed",
        "ADR",
    ]:
        if phrase not in lifecycle:
            failures.append(f"Issue lifecycle missing {phrase}")
    ladder = _read(ROOT / "docs" / "contributor-ladder.md")
    for phrase in [
        "Contributor",
        "Regular contributor",
        "Maintainer",
        "Agent contributor",
        "validation",
    ]:
        if phrase not in ladder:
            failures.append(f"Contributor ladder missing {phrase}")
    template = _read(ROOT / "docs" / "adr" / "template.md")
    for phrase in ["Status", "Context", "Decision", "Consequences", "Validation"]:
        if phrase not in template:
            failures.append(f"ADR template missing {phrase}")
    for relative in [
        ".github/labels.yml",
        ".github/workflows/sync-labels.yml",
        ".github/workflows/auto-label.yml",
        ".github/workflows/stale.yml",
        ".github/workflows/review-evidence-gate.yml",
        ".github/review-evidence-policy.json",
        ".github/PULL_REQUEST_TEMPLATE.md",
        ".github/CODEOWNERS",
        "docs/elevated-review-policy.md",
    ]:
        if not (ROOT / relative).exists():
            failures.append(f"Missing governance automation file: {relative}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Governance lifecycle checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
