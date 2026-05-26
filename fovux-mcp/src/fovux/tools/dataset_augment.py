"""dataset_augment — create a local augmented YOLO dataset copy."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any, cast

from PIL import Image, ImageDraw

from fovux.core.dataset_config import validate_yolo_data_yaml
from fovux.core.errors import FovuxDatasetNotFoundError
from fovux.core.tooling import tool_event
from fovux.schemas.dataset import AugmentationTechnique, DatasetAugmentInput, DatasetAugmentOutput
from fovux.server import mcp


@mcp.tool()
def dataset_augment(
    dataset_path: str,
    techniques: list[str] | None = None,
    multiplier: int = 3,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Augment a YOLO dataset with deterministic local transforms."""
    if output_path is None:
        raise ValueError("output_path is required for dataset_augment")
    inp = DatasetAugmentInput(
        dataset_path=Path(dataset_path),
        techniques=cast(list[AugmentationTechnique], techniques or ["flip_h"]),
        multiplier=multiplier,
        output_path=Path(output_path),
    )
    with tool_event("dataset_augment", dataset_path=dataset_path, output_path=output_path):
        return _run_dataset_augment(inp).model_dump(mode="json")


def _run_dataset_augment(inp: DatasetAugmentInput) -> DatasetAugmentOutput:
    source = inp.dataset_path.expanduser().resolve()
    if not source.exists():
        raise FovuxDatasetNotFoundError(str(source))
    validate_yolo_data_yaml(source)

    output = inp.output_path.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    for yaml_name in ("data.yaml", "dataset.yaml"):
        if (source / yaml_name).exists():
            shutil.copy2(source / yaml_name, output / yaml_name)
            break

    image_paths = _find_images(source / "images")
    generated = 0
    manifest: list[dict[str, object]] = []
    started = time.perf_counter()

    for image_path in image_paths:
        split = _split_for_image(source, image_path)
        label_path = _label_for_image(source, image_path, split)
        for index in range(max(inp.multiplier, 0)):
            technique = inp.techniques[index % len(inp.techniques)]
            target_image = (
                output / "images" / split / f"{image_path.stem}_aug{index}{image_path.suffix}"
            )
            target_label = output / "labels" / split / f"{image_path.stem}_aug{index}.txt"
            target_image.parent.mkdir(parents=True, exist_ok=True)
            target_label.parent.mkdir(parents=True, exist_ok=True)
            _write_augmented_image(image_path, target_image, technique)
            _write_augmented_label(label_path, target_label, technique)
            generated += 1
            manifest.append(
                {
                    "source_image": str(image_path),
                    "image": str(target_image),
                    "label": str(target_label),
                    "technique": technique,
                }
            )

    manifest_path = output / "augmentation_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "source_images": len(image_paths),
                "generated_images": generated,
                "duration_seconds": round(time.perf_counter() - started, 6),
                "items": manifest,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return DatasetAugmentOutput(
        dataset_path=source,
        output_path=output,
        source_images=len(image_paths),
        generated_images=generated,
        techniques=list(inp.techniques),
        manifest_path=manifest_path,
    )


def _find_images(root: Path) -> list[Path]:
    image_exts = {".jpg", ".jpeg", ".png", ".bmp"}
    return sorted(path for path in root.rglob("*") if path.suffix.lower() in image_exts)


def _split_for_image(dataset: Path, image_path: Path) -> str:
    relative = image_path.relative_to(dataset / "images")
    return relative.parts[0] if len(relative.parts) > 1 else "train"


def _label_for_image(dataset: Path, image_path: Path, split: str) -> Path:
    return dataset / "labels" / split / f"{image_path.stem}.txt"


def _write_augmented_image(source: Path, target: Path, technique: str) -> None:
    with Image.open(source) as image:
        if technique == "flip_h":
            out = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif technique == "flip_v":
            out = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        elif technique == "cutout":
            out = image.copy()
            draw = ImageDraw.Draw(out)
            width, height = out.size
            draw.rectangle(
                (width * 0.35, height * 0.35, width * 0.65, height * 0.65),
                fill=(0, 0, 0),
            )
        else:
            out = image.copy()
        out.save(target)


def _write_augmented_label(source: Path, target: Path, technique: str) -> None:
    if not source.exists():
        target.write_text("", encoding="utf-8")
        return
    lines: list[str] = []
    for raw in source.read_text(encoding="utf-8").splitlines():
        parts = raw.split()
        if len(parts) < 5:
            continue
        class_id, cx, cy, width, height = parts[:5]
        x = float(cx)
        y = float(cy)
        if technique == "flip_h":
            x = 1.0 - x
        elif technique == "flip_v":
            y = 1.0 - y
        lines.append(f"{class_id} {x:.6f} {y:.6f} {float(width):.6f} {float(height):.6f}")
    target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
