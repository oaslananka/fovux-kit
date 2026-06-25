"""Validate dataset intelligence and remediation coverage."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    schema = _read(ROOT / "fovux-mcp" / "src" / "fovux" / "schemas" / "dataset.py")
    for phrase in [
        "auto_fix_plan",
        "dataset_card",
        "quality_score",
        "remediation_script",
        "duplicate_groups",
    ]:
        if phrase not in schema:
            failures.append(f"Dataset schema missing {phrase}")
    inspect_tool = _read(
        ROOT / "fovux-mcp" / "src" / "fovux" / "tools" / "dataset_inspect.py"
    )
    for phrase in [
        "Remove duplicate images",
        "Remove train-val/test leakage",
        "quality_score",
    ]:
        if phrase not in inspect_tool:
            failures.append(f"dataset_inspect missing {phrase}")
    validate_tool = _read(
        ROOT / "fovux-mcp" / "src" / "fovux" / "tools" / "dataset_validate.py"
    )
    for phrase in ["remediation_script", "errors", "warnings", "valid"]:
        if phrase.lower() not in validate_tool.lower():
            failures.append(f"dataset_validate missing {phrase}")
    golden = _read(
        ROOT / "fovux-mcp" / "tests" / "unit" / "tools" / "test_golden_dataset.py"
    )
    for phrase in [
        "Corrupt images",
        "Missing labels",
        "Train/val leakage",
        "Class mismatch",
        "Windows path slashes",
    ]:
        if phrase not in golden:
            failures.append(f"golden dataset fixture missing {phrase}")
    docs = _read(ROOT / "docs" / "dataset-intelligence-contract.md")
    for phrase in [
        "Missing images",
        "Malformed YOLO",
        "Duplicate images",
        "Train/val/test leakage",
        "Class imbalance",
        "Tiny/huge boxes",
    ]:
        if phrase not in docs:
            failures.append(f"dataset intelligence docs missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Dataset intelligence checks passed: validation, inspection, duplicates, leakage, remediation, and golden fixtures are covered."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
