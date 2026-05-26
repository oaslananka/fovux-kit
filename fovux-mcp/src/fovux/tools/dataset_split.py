"""dataset_split — create stratified train/val/test splits."""

from __future__ import annotations

import json
import random
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from fovux.core.dataset_utils import (
    detect_format,
    iter_yolo_labels,
    parse_yolo_label,
)
from fovux.core.errors import (
    FovuxDatasetEmptyError,
    FovuxDatasetFormatError,
    FovuxDatasetNotFoundError,
)
from fovux.core.paths import get_fovux_home
from fovux.core.tooling import tool_event
from fovux.core.validation import ensure_writable_output
from fovux.schemas.dataset import DatasetSplitInput, DatasetSplitOutput
from fovux.server import mcp


@mcp.tool()
def dataset_split(
    dataset_path: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
    stratify_by_class: bool = True,
    seed: int = 42,
    output_format: str = "yolo",
    overwrite: bool = False,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Create or re-create train/val/test splits with optional class stratification.

    Writes a split_manifest.json for reproducibility. Supports YOLO output format.
    """
    inp = DatasetSplitInput(
        dataset_path=Path(dataset_path),
        ratios=(train_ratio, val_ratio, test_ratio),
        stratify_by_class=stratify_by_class,
        seed=seed,
        output_format=output_format,  # type: ignore[arg-type]
        overwrite=overwrite,
        output_path=Path(output_path) if output_path else None,
    )
    with tool_event(
        "dataset_split",
        dataset_path=dataset_path,
        output_format=output_format,
        seed=seed,
    ):
        return _run_split(inp).model_dump(mode="json")


def _run_split(inp: DatasetSplitInput) -> DatasetSplitOutput:
    path = inp.dataset_path.expanduser().resolve()
    if not path.exists():
        raise FovuxDatasetNotFoundError(str(path))

    fmt = detect_format(path)
    if fmt != "yolo":
        raise FovuxDatasetFormatError("dataset_split currently supports YOLO format only.")

    # Collect all image/label pairs
    pairs: list[tuple[Path, Path]] = list(iter_yolo_labels(path))
    if not pairs:
        raise FovuxDatasetEmptyError(str(path))

    rng = random.Random(inp.seed)  # noqa: S311 - deterministic split seed, not crypto

    if inp.stratify_by_class:
        # Group images by dominant class
        class_to_pairs: dict[int, list[tuple[Path, Path]]] = defaultdict(list)
        no_ann: list[tuple[Path, Path]] = []
        for img_p, lbl_p in pairs:
            anns = parse_yolo_label(lbl_p) if lbl_p.exists() else []
            if not anns:
                no_ann.append((img_p, lbl_p))
            else:
                dominant = max(
                    {annotation[0] for annotation in anns},
                    key=lambda class_id: sum(1 for annotation in anns if annotation[0] == class_id),
                )
                class_to_pairs[dominant].append((img_p, lbl_p))

        train_pairs: list[tuple[Path, Path]] = []
        val_pairs: list[tuple[Path, Path]] = []
        test_pairs: list[tuple[Path, Path]] = []

        for cls_pairs in class_to_pairs.values():
            rng.shuffle(cls_pairs)
            n = len(cls_pairs)
            n_train, n_val, _ = _split_counts(n, inp.ratios)
            train_pairs.extend(cls_pairs[:n_train])
            val_pairs.extend(cls_pairs[n_train : n_train + n_val])
            test_pairs.extend(cls_pairs[n_train + n_val :])

        rng.shuffle(no_ann)
        n = len(no_ann)
        n_train, n_val, _ = _split_counts(n, inp.ratios)
        train_pairs.extend(no_ann[:n_train])
        val_pairs.extend(no_ann[n_train : n_train + n_val])
        test_pairs.extend(no_ann[n_train + n_val :])
    else:
        all_pairs = list(pairs)
        rng.shuffle(all_pairs)
        n = len(all_pairs)
        n_train, n_val, _ = _split_counts(n, inp.ratios)
        train_pairs = all_pairs[:n_train]
        val_pairs = all_pairs[n_train : n_train + n_val]
        test_pairs = all_pairs[n_train + n_val :]

    output_path = ensure_writable_output(
        inp.output_path if inp.output_path is not None else path / "split_output",
        allowed_roots=[
            get_fovux_home(),
            Path.cwd(),
            Path(tempfile.gettempdir()),
            path,
            path.parent,
        ],
    )
    if output_path.exists() and not inp.overwrite:
        raise FovuxDatasetFormatError(f"Output path {output_path} exists. Use overwrite=True.")
    if output_path.exists():
        shutil.rmtree(output_path)

    _write_yolo_split(output_path, "train", train_pairs)
    _write_yolo_split(output_path, "val", val_pairs)
    _write_yolo_split(output_path, "test", test_pairs)

    # Copy data.yaml
    src_yaml = path / "data.yaml"
    if src_yaml.exists():
        shutil.copy(src_yaml, output_path / "data.yaml")

    # Write manifest
    manifest = {
        "seed": inp.seed,
        "ratios": list(inp.ratios),
        "stratify_by_class": inp.stratify_by_class,
        "train": [str(p[0]) for p in train_pairs],
        "val": [str(p[0]) for p in val_pairs],
        "test": [str(p[0]) for p in test_pairs],
    }
    manifest_path = output_path / "split_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    # Build stratification report
    strat_report: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for split_name, split_pairs in [
        ("train", train_pairs),
        ("val", val_pairs),
        ("test", test_pairs),
    ]:
        for _, lbl_p in split_pairs:
            for cls, *_ in parse_yolo_label(lbl_p):
                strat_report[str(cls)][split_name] += 1

    return DatasetSplitOutput(
        train_count=len(train_pairs),
        val_count=len(val_pairs),
        test_count=len(test_pairs),
        stratification_report={k: dict(v) for k, v in strat_report.items()},
        output_path=output_path,
        manifest_path=manifest_path,
    )


def _write_yolo_split(output_path: Path, split: str, pairs: list[tuple[Path, Path]]) -> None:
    (output_path / "images" / split).mkdir(parents=True, exist_ok=True)
    (output_path / "labels" / split).mkdir(parents=True, exist_ok=True)
    for img_p, lbl_p in pairs:
        if img_p.exists():
            shutil.copy(img_p, output_path / "images" / split / img_p.name)
        if lbl_p.exists():
            shutil.copy(lbl_p, output_path / "labels" / split / lbl_p.name)


def _split_counts(n_items: int, ratios: tuple[float, float, float]) -> tuple[int, int, int]:
    if n_items <= 0:
        return 0, 0, 0
    train_count = round(n_items * ratios[0])
    val_count = round(n_items * ratios[1])
    train_count = min(train_count, n_items)
    val_count = min(val_count, n_items - train_count)
    test_count = n_items - train_count - val_count
    return train_count, val_count, test_count
