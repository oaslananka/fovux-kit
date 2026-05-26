"""Strict dataset configuration validation for YOLO data.yaml files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fovux.core.errors import FovuxDatasetFormatError

ALLOWED_YOLO_KEYS = {"path", "train", "val", "test", "nc", "names", "kpt_shape"}
PATH_KEYS = {"path", "train", "val", "test"}
UNSAFE_YAML_TOKENS = ("!!python/", "!!python:", "tag:yaml.org,2002:python")


def validate_yolo_data_yaml(dataset_root: Path) -> dict[str, Any]:
    """Parse and validate a YOLO dataset YAML file using safe rules."""
    import yaml  # type: ignore[import-untyped]

    yaml_path = _find_yolo_yaml(dataset_root)
    text = yaml_path.read_text(encoding="utf-8")
    if any(token in text for token in UNSAFE_YAML_TOKENS):
        raise FovuxDatasetFormatError(
            f"Unsafe YAML tag found in {yaml_path.name}.",
            hint="Remove Python-specific YAML tags; Fovux only accepts plain YOLO dataset YAML.",
        )

    loaded = yaml.safe_load(text) or {}
    if not isinstance(loaded, dict):
        raise FovuxDatasetFormatError(
            f"{yaml_path.name} must contain a mapping.",
            hint="Use standard YOLO keys such as path, train, val, nc, and names.",
        )

    data = cast(dict[str, Any], loaded)
    unknown = sorted(set(data) - ALLOWED_YOLO_KEYS)
    if unknown:
        raise FovuxDatasetFormatError(
            f"{yaml_path.name} contains unsupported keys: {', '.join(unknown)}.",
            hint=f"Allowed keys are: {', '.join(sorted(ALLOWED_YOLO_KEYS))}.",
        )

    root = _resolve_dataset_root(dataset_root, data.get("path"))
    for key in PATH_KEYS - {"path"}:
        value = data.get(key)
        if value is None:
            continue
        _validate_yaml_path_value(root, value, key)

    names = data.get("names")
    if names is not None and not isinstance(names, (list, dict)):
        raise FovuxDatasetFormatError(
            f"{yaml_path.name} field 'names' must be a list or mapping.",
            hint="Use names: ['class_a', 'class_b'] or names: {0: class_a}.",
        )

    return data


def _find_yolo_yaml(dataset_root: Path) -> Path:
    for name in ("data.yaml", "dataset.yaml"):
        yaml_path = dataset_root / name
        if yaml_path.exists():
            return yaml_path
    raise FovuxDatasetFormatError(
        f"No YOLO data.yaml found under {dataset_root}.",
        hint="Create data.yaml or dataset.yaml at the dataset root.",
    )


def _resolve_dataset_root(dataset_root: Path, configured_root: object) -> Path:
    if configured_root is None:
        return dataset_root.resolve()
    if not isinstance(configured_root, str):
        raise FovuxDatasetFormatError(
            "YOLO data.yaml field 'path' must be a string when provided.",
            hint="Use a relative or absolute dataset root path.",
        )
    root = Path(configured_root)
    if not root.is_absolute():
        root = dataset_root / root
    return root.resolve()


def _validate_yaml_path_value(root: Path, value: object, key: str) -> None:
    values = value if isinstance(value, list) else [value]
    for item in values:
        if not isinstance(item, str):
            raise FovuxDatasetFormatError(
                f"YOLO data.yaml field '{key}' must be a string or list of strings.",
                hint="Use relative paths such as images/train.",
            )
        candidate = Path(item)
        if not candidate.is_absolute():
            candidate = root / candidate
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root)
        except ValueError as exc:
            raise FovuxDatasetFormatError(
                f"YOLO data.yaml field '{key}' escapes the dataset root: {item}",
                hint="Keep train/val/test paths inside the dataset root.",
            ) from exc
