"""dataset_convert — convert between YOLO, COCO, and VOC formats."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from fovux.core.dataset_utils import (
    detect_format,
    find_coco_jsons,
    iter_yolo_labels,
    parse_yolo_label,
    read_coco_json,
    read_yolo_data_yaml,
)
from fovux.core.errors import FovuxDatasetFormatError, FovuxDatasetNotFoundError
from fovux.core.paths import get_fovux_home
from fovux.core.tooling import tool_event
from fovux.core.validation import (
    ensure_within_root,
    ensure_writable_output,
    resolve_local_path,
    validate_file_size,
)
from fovux.schemas.dataset import DatasetConvertInput, DatasetConvertOutput
from fovux.server import mcp


@mcp.tool()
def dataset_convert(
    source_path: str,
    target_path: str,
    target_format: str,
    source_format: str = "auto",
    copy_images: bool = False,
    class_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Convert a dataset between YOLO, COCO, and VOC formats.

    class_map renames classes: {'cat': 'feline'}. Use copy_images=True to copy images.
    """
    inp = DatasetConvertInput(
        source_path=Path(source_path),
        source_format=source_format,  # type: ignore[arg-type]
        target_format=target_format,  # type: ignore[arg-type]
        target_path=Path(target_path),
        copy_images=copy_images,
        class_map=class_map,
    )
    with tool_event(
        "dataset_convert",
        source_path=source_path,
        target_path=target_path,
        source_format=source_format,
        target_format=target_format,
    ):
        return _run_convert(inp).model_dump(mode="json")


def _run_convert(inp: DatasetConvertInput) -> DatasetConvertOutput:
    t0 = time.perf_counter()
    src = resolve_local_path(inp.source_path)
    dst = ensure_writable_output(
        resolve_local_path(inp.target_path),
        allowed_roots=[get_fovux_home(), Path.cwd(), Path(tempfile.gettempdir()), src, src.parent],
    )

    if not src.exists():
        raise FovuxDatasetNotFoundError(str(src))

    src_fmt = inp.source_format if inp.source_format != "auto" else detect_format(src)

    if src_fmt == inp.target_format:
        raise FovuxDatasetFormatError(
            f"Source and target format are both '{src_fmt}'. Nothing to convert."
        )

    if src_fmt == "yolo" and inp.target_format == "coco":
        return _yolo_to_coco(src, dst, inp, t0)
    if src_fmt == "coco" and inp.target_format == "yolo":
        return _coco_to_yolo(src, dst, inp, t0)

    raise FovuxDatasetFormatError(
        (
            "dataset_convert currently supports YOLO → COCO and COCO → YOLO only; "
            f"received {src_fmt} → {inp.target_format}."
        ),
        hint="Convert through YOLO or COCO for v1.0.0 workflows.",
    )


def _yolo_to_coco(
    src: Path, dst: Path, inp: DatasetConvertInput, t0: float
) -> DatasetConvertOutput:
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "annotations").mkdir(exist_ok=True)

    meta = read_yolo_data_yaml(src)
    class_names: list[str] = meta.get("names", [])
    if isinstance(class_names, dict):
        class_names = list(class_names.values())

    if inp.class_map:
        class_names = [inp.class_map.get(n, n) for n in class_names]

    categories = [
        {"id": i, "name": name, "supercategory": "object"} for i, name in enumerate(class_names)
    ]

    split_docs: dict[str, dict[str, Any]] = {}
    image_id = 0
    ann_id = 0
    converted = 0
    skipped = 0
    skip_reasons: dict[str, int] = {}

    for img_path, label_path in iter_yolo_labels(src):
        if not img_path.exists():
            skipped += 1
            skip_reasons["missing_image"] = skip_reasons.get("missing_image", 0) + 1
            continue

        try:
            from PIL import Image

            safe_img_path = ensure_within_root(img_path, src)
            validate_file_size(safe_img_path)
            with Image.open(safe_img_path) as im:
                w, h = im.size
        except Exception:
            skipped += 1
            skip_reasons["unreadable_image"] = skip_reasons.get("unreadable_image", 0) + 1
            continue

        split_name = _infer_split_name(img_path, src)
        document = split_docs.setdefault(
            split_name,
            {
                "info": {"description": "Converted by Fovux", "version": "2.0"},
                "categories": categories,
                "images": [],
                "annotations": [],
            },
        )
        document["images"].append(
            {
                "id": image_id,
                "file_name": img_path.name,
                "width": w,
                "height": h,
            }
        )

        if inp.copy_images:
            split_images_dir = dst / "images" / split_name
            split_images_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy(safe_img_path, split_images_dir / img_path.name)

        for cls, cx, cy, bw, bh in parse_yolo_label(label_path):
            x = (cx - bw / 2) * w
            y = (cy - bh / 2) * h
            bw_px = bw * w
            bh_px = bh * h
            document["annotations"].append(
                {
                    "id": ann_id,
                    "image_id": image_id,
                    "category_id": cls,
                    "bbox": [round(x, 2), round(y, 2), round(bw_px, 2), round(bh_px, 2)],
                    "area": round(bw_px * bh_px, 2),
                    "iscrowd": 0,
                }
            )
            ann_id += 1
            converted += 1

        image_id += 1

    for split_name, document in split_docs.items():
        (dst / "annotations" / f"instances_{split_name}.json").write_text(
            json.dumps(document, indent=2),
            encoding="utf-8",
        )
    return DatasetConvertOutput(
        images_processed=image_id,
        annotations_converted=converted,
        annotations_skipped=skipped,
        skip_reasons=skip_reasons,
        target_path=dst,
        conversion_duration_seconds=round(time.perf_counter() - t0, 3),
    )


def _coco_to_yolo(
    src: Path, dst: Path, inp: DatasetConvertInput, t0: float
) -> DatasetConvertOutput:
    dst.mkdir(parents=True, exist_ok=True)
    (dst / "images").mkdir(exist_ok=True)
    (dst / "labels").mkdir(exist_ok=True)

    json_files = find_coco_jsons(src)
    if not json_files:
        raise FovuxDatasetFormatError(f"No COCO JSON files found in {src}/annotations/")

    converted = 0
    skipped = 0
    skip_reasons: dict[str, int] = {}
    images_processed = 0
    categories_by_json: dict[str, dict[int, str]] = {}

    for jf in json_files:
        data = read_coco_json(jf)
        categories_by_json[str(jf)] = {
            int(cat["id"]): str(cat["name"]) for cat in data.get("categories", [])
        }

    unified_categories: dict[int, str] = {}
    conflicting_categories: list[str] = []
    for source_name, mapping in categories_by_json.items():
        for category_id, category_name in mapping.items():
            existing = unified_categories.get(category_id)
            if existing is not None and existing != category_name:
                conflicting_categories.append(
                    f"{source_name}: category id {category_id} is "
                    f"'{category_name}' but was '{existing}'"
                )
                continue
            unified_categories[category_id] = category_name

    if conflicting_categories:
        raise FovuxDatasetFormatError(
            "COCO category definitions disagree across annotation files: "
            + "; ".join(conflicting_categories)
        )

    ordered_categories = sorted(unified_categories.items(), key=lambda item: item[0])
    class_names = [name for _, name in ordered_categories]
    id_to_idx = {category_id: index for index, (category_id, _) in enumerate(ordered_categories)}

    for jf in json_files:
        data = read_coco_json(jf)
        img_map = {img["id"]: img for img in data.get("images", [])}
        ann_by_img: dict[int, list[dict[str, Any]]] = {}
        for ann in data.get("annotations", []):
            ann_by_img.setdefault(ann["image_id"], []).append(ann)

        images_dir = src / "images"
        split_name = jf.stem.replace("instances_", "", 1)
        split_images_dir = dst / "images" / split_name
        split_labels_dir = dst / "labels" / split_name
        split_images_dir.mkdir(parents=True, exist_ok=True)
        split_labels_dir.mkdir(parents=True, exist_ok=True)
        for img_id, img_info in img_map.items():
            images_processed += 1
            fname = img_info["file_name"]
            iw, ih = img_info.get("width", 1), img_info.get("height", 1)
            src_img = images_dir / fname
            if inp.copy_images and src_img.exists():
                safe_img = ensure_within_root(src_img, src)
                validate_file_size(safe_img)
                shutil.copy(safe_img, split_images_dir / Path(fname).name)

            lines = []
            for ann in ann_by_img.get(img_id, []):
                cat_id = ann["category_id"]
                cls_idx = id_to_idx.get(cat_id, 0)
                x, y, bw, bh = ann["bbox"]
                cx = (x + bw / 2) / iw
                cy = (y + bh / 2) / ih
                nw = bw / iw
                nh = bh / ih
                lines.append(f"{cls_idx} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}")
                converted += 1

            stem = Path(fname).stem
            (split_labels_dir / f"{stem}.txt").write_text("\n".join(lines), encoding="utf-8")

    yaml_content = (
        "path: .\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        f"nc: {len(class_names)}\n"
        f"names: {class_names}\n"
    )
    (dst / "data.yaml").write_text(yaml_content, encoding="utf-8")

    return DatasetConvertOutput(
        images_processed=images_processed,
        annotations_converted=converted,
        annotations_skipped=skipped,
        skip_reasons=skip_reasons,
        target_path=dst,
        conversion_duration_seconds=round(time.perf_counter() - t0, 3),
    )


def _infer_split_name(image_path: Path, dataset_root: Path) -> str:
    relative = image_path.relative_to(dataset_root)
    parts = [part.lower() for part in relative.parts]
    for split in ("train", "val", "test"):
        if split in parts:
            return split
    return "all"
