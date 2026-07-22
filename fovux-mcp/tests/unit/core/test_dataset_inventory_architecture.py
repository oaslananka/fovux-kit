"""Architecture budgets for the normalized dataset inventory boundary."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[3]


def _function_lengths(path: Path) -> dict[str, int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: (node.end_lineno or node.lineno) - node.lineno + 1
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_inspect_and_validate_depend_on_the_normalized_inventory() -> None:
    inspect_source = (ROOT / "src/fovux/tools/dataset_inspect.py").read_text(encoding="utf-8")
    validate_source = (ROOT / "src/fovux/tools/dataset_validate.py").read_text(encoding="utf-8")

    assert "build_dataset_inventory(" in inspect_source
    assert "build_dataset_inventory(" in validate_source
    assert "_inspect_yolo" not in inspect_source
    assert "_inspect_coco" not in inspect_source


def test_dataset_boundary_stays_within_agreed_complexity_size_budgets() -> None:
    inspect = ROOT / "src/fovux/tools/dataset_inspect.py"
    validate = ROOT / "src/fovux/tools/dataset_validate.py"
    adapters = ROOT / "src/fovux/core/dataset_adapters.py"

    assert len(inspect.read_text(encoding="utf-8").splitlines()) <= 450
    assert len(validate.read_text(encoding="utf-8").splitlines()) <= 250
    assert len(adapters.read_text(encoding="utf-8").splitlines()) <= 500

    inspect_lengths = _function_lengths(inspect)
    validate_lengths = _function_lengths(validate)
    adapter_lengths = _function_lengths(adapters)
    assert max(inspect_lengths.values()) <= 90
    assert max(validate_lengths.values()) <= 80
    assert max(adapter_lengths.values()) <= 140


def test_inventory_extension_point_and_adr_are_documented() -> None:
    inventory = (ROOT / "src/fovux/core/dataset_inventory.py").read_text(encoding="utf-8")
    adr = ROOT / "docs/adr/0009-normalized-dataset-inventory.md"

    assert "class DatasetFormatAdapter(Protocol)" in inventory
    assert "register_dataset_adapter" in inventory
    assert adr.is_file()
    text = adr.read_text(encoding="utf-8")
    for phrase in (
        "DatasetInventory",
        "YOLO",
        "COCO",
        "dependency direction",
        "backward compatible",
    ):
        assert phrase in text
