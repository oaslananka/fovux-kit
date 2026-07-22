"""Built-in YOLO and COCO adapters for the normalized dataset inventory."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from fovux.core.dataset_inventory import (
    AnnotationRecord,
    DatasetFinding,
    DatasetFormat,
    DatasetInventory,
    ImageRecord,
    NormalizedBoundingBox,
)
from fovux.core.dataset_utils import (
    find_coco_jsons,
    find_images,
    read_coco_json,
    read_yolo_data_yaml,
)
from fovux.core.errors import FovuxDatasetEmptyError
from fovux.core.validation import ensure_within_root, validate_file_size


class YoloDatasetAdapter:
    """Translate a YOLO directory layout into the shared inventory."""

    format_name: DatasetFormat = "yolo"

    def build(
        self,
        root: Path,
        *,
        analyze_images: bool,
        compute_fingerprints: bool,
        max_images_analyzed: int,
    ) -> DatasetInventory:
        """Build a normalized inventory from a YOLO directory layout."""
        class_names, declared_count, findings, warnings = _read_yolo_classes(root)
        images_root = root / "images"
        labels_root = root / "labels"
        image_paths = find_images(images_root)
        if not image_paths:
            raise FovuxDatasetEmptyError(str(root))

        images: list[ImageRecord] = []
        annotations: list[AnnotationRecord] = []
        splits: Counter[str] = Counter()
        for index, image_path in enumerate(image_paths):
            relative = image_path.relative_to(images_root)
            split = relative.parts[0] if len(relative.parts) > 1 else "root"
            label_path = labels_root / relative.with_suffix(".txt")
            image = _build_image_record(
                root=root,
                image_id=relative.as_posix(),
                image_path=image_path,
                split=split,
                annotation_source=label_path,
                annotation_source_exists=label_path.is_file(),
                analyzed=index < max_images_analyzed,
                analyze_images=analyze_images,
                compute_fingerprints=compute_fingerprints,
                declared_width=None,
                declared_height=None,
            )
            images.append(image)
            splits[split] += 1
            if label_path.is_file():
                parsed, parse_findings = _parse_yolo_label(root, image, label_path)
                annotations.extend(parsed)
                findings.extend(parse_findings)

        orphan_sources = _find_orphan_yolo_labels(root, image_paths)
        findings.extend(
            DatasetFinding(
                code="orphan_annotation",
                severity="warning",
                message="Annotation file has no corresponding image",
                file=source,
            )
            for source in orphan_sources
        )
        return DatasetInventory(
            root=root,
            format="yolo",
            class_names=class_names,
            images=images,
            annotations=annotations,
            splits=dict(sorted(splits.items())),
            findings=findings,
            warnings=warnings,
            orphan_annotation_sources=orphan_sources,
            declared_class_count=declared_count,
        )


class CocoDatasetAdapter:
    """Translate COCO JSON files into the shared inventory."""

    format_name: DatasetFormat = "coco"

    def build(
        self,
        root: Path,
        *,
        analyze_images: bool,
        compute_fingerprints: bool,
        max_images_analyzed: int,
    ) -> DatasetInventory:
        """Build a normalized inventory from COCO annotation documents."""
        json_files = find_coco_jsons(root)
        if not json_files:
            raise FovuxDatasetEmptyError(str(root))

        class_names: dict[int, str] = {}
        images: list[ImageRecord] = []
        annotations: list[AnnotationRecord] = []
        findings: list[DatasetFinding] = []
        warnings: list[str] = []
        splits: Counter[str] = Counter()
        analyzed_count = 0

        for json_path in json_files:
            try:
                data = read_coco_json(json_path)
            except Exception as exc:
                warnings.append(f"Cannot parse {json_path.name}: {exc}")
                findings.append(
                    DatasetFinding(
                        code="metadata_parse_error",
                        severity="warning",
                        message=f"Cannot parse COCO metadata: {exc}",
                        file=json_path,
                    )
                )
                continue

            for category in _mapping_list(data.get("categories")):
                category_id = _as_int(category.get("id"))
                name = category.get("name")
                if category_id is not None and isinstance(name, str):
                    class_names[category_id] = name

            split = _coco_split_name(json_path)
            image_by_local_id: dict[int, ImageRecord] = {}
            for item in _mapping_list(data.get("images")):
                local_id = _as_int(item.get("id"))
                file_name = item.get("file_name")
                if local_id is None or not isinstance(file_name, str):
                    findings.append(
                        DatasetFinding(
                            code="invalid_image_record",
                            severity="error",
                            message="COCO image requires integer id and string file_name",
                            file=json_path,
                        )
                    )
                    continue
                image_path = _resolve_coco_image(root, file_name)
                analyzed = analyzed_count < max_images_analyzed
                if analyzed:
                    analyzed_count += 1
                image = _build_image_record(
                    root=root,
                    image_id=f"{json_path.name}:{local_id}",
                    image_path=image_path,
                    split=split,
                    annotation_source=json_path,
                    annotation_source_exists=True,
                    analyzed=analyzed,
                    analyze_images=analyze_images,
                    compute_fingerprints=compute_fingerprints,
                    declared_width=_as_positive_int(item.get("width")),
                    declared_height=_as_positive_int(item.get("height")),
                )
                images.append(image)
                image_by_local_id[local_id] = image
                splits[split] += 1

            for item in _mapping_list(data.get("annotations")):
                image_local_id = _as_int(item.get("image_id"))
                class_id = _as_int(item.get("category_id"))
                raw_bbox = _as_bbox(item.get("bbox"))
                if image_local_id is None or class_id is None or raw_bbox is None:
                    findings.append(
                        DatasetFinding(
                            code="invalid_annotation_record",
                            severity="error",
                            message="COCO annotation requires image_id, category_id, and bbox",
                            file=json_path,
                        )
                    )
                    continue
                referenced_image = image_by_local_id.get(image_local_id)
                if referenced_image is None:
                    findings.append(
                        DatasetFinding(
                            code="orphan_annotation",
                            severity="error",
                            message=f"Annotation references unknown image id {image_local_id}",
                            file=json_path,
                        )
                    )
                    image_id = f"{json_path.name}:{image_local_id}"
                    annotation_image_path: Path | None = None
                    bbox = None
                else:
                    image_id = referenced_image.image_id
                    annotation_image_path = referenced_image.path
                    bbox = _normalize_coco_bbox(
                        raw_bbox,
                        referenced_image.width,
                        referenced_image.height,
                    )
                annotations.append(
                    AnnotationRecord(
                        image_id=image_id,
                        image_path=annotation_image_path,
                        class_id=class_id,
                        source_path=json_path,
                        line=None,
                        bbox=bbox,
                        raw_bbox=raw_bbox,
                        raw_area=max(0.0, raw_bbox[2]) * max(0.0, raw_bbox[3]),
                    )
                )

        if not images:
            raise FovuxDatasetEmptyError(str(root))
        return DatasetInventory(
            root=root,
            format="coco",
            class_names=dict(sorted(class_names.items())),
            images=images,
            annotations=annotations,
            splits=dict(sorted(splits.items())),
            findings=findings,
            warnings=warnings,
            declared_class_count=len(class_names),
        )


def _read_yolo_classes(
    root: Path,
) -> tuple[dict[int, str], int | None, list[DatasetFinding], list[str]]:
    findings: list[DatasetFinding] = []
    warnings: list[str] = []
    metadata_file = root / "data.yaml"
    try:
        metadata = read_yolo_data_yaml(root)
    except Exception as exc:
        warning = "Could not parse data.yaml — class names unknown."
        warnings.append(warning)
        findings.append(
            DatasetFinding(
                code="metadata_parse_error",
                severity="warning",
                message=f"Cannot parse data.yaml: {exc}",
                file=metadata_file,
            )
        )
        return {}, None, findings, warnings

    names = metadata.get("names", [])
    if isinstance(names, Mapping):
        class_names = {
            key: str(value)
            for raw_key, value in names.items()
            if (key := _as_int(raw_key)) is not None
        }
    elif isinstance(names, list):
        class_names = {index: str(value) for index, value in enumerate(names)}
    else:
        class_names = {}
    class_names = dict(sorted(class_names.items()))
    declared_count = _as_positive_int(metadata.get("nc"))
    if declared_count and class_names and declared_count != len(class_names):
        findings.append(
            DatasetFinding(
                code="class_count_mismatch",
                severity="error",
                message=(
                    f"Class count nc ({declared_count}) does not match length of names list "
                    f"({len(class_names)})"
                ),
                file=metadata_file,
            )
        )
    return class_names, declared_count, findings, warnings


def _build_image_record(
    *,
    root: Path,
    image_id: str,
    image_path: Path,
    split: str,
    annotation_source: Path | None,
    annotation_source_exists: bool,
    analyzed: bool,
    analyze_images: bool,
    compute_fingerprints: bool,
    declared_width: int | None,
    declared_height: int | None,
) -> ImageRecord:
    exists = image_path.is_file()
    width, height = declared_width, declared_height
    readable: bool | None = None
    fingerprint: str | None = None
    analysis_error: str | None = None
    if analyze_images and analyzed:
        if not exists:
            readable = False
            analysis_error = "Image file does not exist"
        else:
            try:
                from PIL import Image

                safe_path = ensure_within_root(image_path, root)
                validate_file_size(safe_path)
                with Image.open(safe_path) as image:
                    width, height = image.size
                    if compute_fingerprints:
                        import imagehash

                        fingerprint = str(imagehash.phash(image))
                    else:
                        image.verify()
                readable = True
            except Exception as exc:
                readable = False
                analysis_error = str(exc)
    return ImageRecord(
        image_id=image_id,
        path=image_path,
        split=split,
        width=width,
        height=height,
        annotation_source=annotation_source,
        annotation_source_exists=annotation_source_exists,
        analyzed=analyzed,
        exists=exists,
        readable=readable,
        fingerprint=fingerprint,
        analysis_error=analysis_error,
    )


def _parse_yolo_label(
    root: Path,
    image: ImageRecord,
    label_path: Path,
) -> tuple[list[AnnotationRecord], list[DatasetFinding]]:
    annotations: list[AnnotationRecord] = []
    findings: list[DatasetFinding] = []
    safe_path = ensure_within_root(label_path, root)
    validate_file_size(safe_path)
    for line_no, line in enumerate(safe_path.read_text(encoding="utf-8").splitlines(), start=1):
        parts = line.strip().split()
        if not parts:
            continue
        if len(parts) < 5:
            findings.append(
                DatasetFinding(
                    code="malformed_annotation",
                    severity="error",
                    message="YOLO annotation requires class id and four bbox values",
                    file=label_path,
                    line=line_no,
                )
            )
            continue
        try:
            class_id = int(parts[0])
            center_x, center_y, width, height = (float(value) for value in parts[1:5])
        except ValueError:
            findings.append(
                DatasetFinding(
                    code="malformed_annotation",
                    severity="error",
                    message="YOLO annotation contains non-numeric values",
                    file=label_path,
                    line=line_no,
                )
            )
            continue
        annotations.append(
            AnnotationRecord(
                image_id=image.image_id,
                image_path=image.path,
                class_id=class_id,
                source_path=label_path,
                line=line_no,
                bbox=NormalizedBoundingBox(
                    x_min=center_x - width / 2,
                    y_min=center_y - height / 2,
                    x_max=center_x + width / 2,
                    y_max=center_y + height / 2,
                ),
                raw_bbox=(center_x, center_y, width, height),
                raw_area=max(0.0, width) * max(0.0, height),
            )
        )
    return annotations, findings


def _find_orphan_yolo_labels(root: Path, image_paths: list[Path]) -> list[Path]:
    images_root, labels_root = root / "images", root / "labels"
    if not labels_root.is_dir():
        return []
    image_stems = {
        image.relative_to(images_root).with_suffix("").as_posix() for image in image_paths
    }
    return [
        label
        for label in sorted(labels_root.rglob("*.txt"))
        if label.relative_to(labels_root).with_suffix("").as_posix() not in image_stems
    ]


def _normalize_coco_bbox(
    raw_bbox: tuple[float, float, float, float],
    width: int | None,
    height: int | None,
) -> NormalizedBoundingBox | None:
    if not width or not height:
        return None
    x, y, box_width, box_height = raw_bbox
    return NormalizedBoundingBox(
        x_min=x / width,
        y_min=y / height,
        x_max=(x + box_width) / width,
        y_max=(y + box_height) / height,
    )


def _resolve_coco_image(root: Path, file_name: str) -> Path:
    relative = Path(file_name)
    candidates = tuple(
        ensure_within_root(candidate, root)
        for candidate in (root / "images" / relative, root / relative)
    )
    return next((path for path in candidates if path.is_file()), candidates[0])


def _mapping_list(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _as_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _as_positive_int(value: object) -> int | None:
    result = _as_int(value)
    return result if result is not None and result > 0 else None


def _as_bbox(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, list) or len(value) < 4:
        return None
    try:
        x, y, width, height = (float(item) for item in value[:4])
    except (TypeError, ValueError):
        return None
    return x, y, width, height


def _coco_split_name(json_path: Path) -> str:
    return json_path.stem.split("_")[-1] if "_" in json_path.stem else json_path.stem
