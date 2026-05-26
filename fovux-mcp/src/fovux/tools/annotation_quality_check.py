"""annotation_quality_check — inspect YOLO labels for common quality issues."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from fovux.core.dataset_utils import iter_yolo_labels, parse_yolo_label, read_yolo_data_yaml
from fovux.core.errors import FovuxDatasetNotFoundError
from fovux.core.tooling import tool_event
from fovux.schemas.diagnostics import (
    AnnotationIssue,
    AnnotationQualityCheckInput,
    AnnotationQualityCheckOutput,
)
from fovux.server import mcp

_SMALL_BOX_AREA = 0.0005
_OVERLAP_THRESHOLD = 0.9
_MAX_OBJECTS_PER_IMAGE = 500


@mcp.tool()
def annotation_quality_check(
    dataset_path: str,
    checks: list[str] | None = None,
) -> dict[str, Any]:
    """Inspect YOLO annotations for out-of-bounds boxes, empty labels, and overlap issues."""
    inp = AnnotationQualityCheckInput(dataset_path=Path(dataset_path), checks=checks or [])
    with tool_event("annotation_quality_check", dataset_path=dataset_path):
        return _run_annotation_quality_check(inp).model_dump(mode="json")


def _run_annotation_quality_check(inp: AnnotationQualityCheckInput) -> AnnotationQualityCheckOutput:
    dataset_path = inp.dataset_path.expanduser().resolve()
    if not dataset_path.exists():
        raise FovuxDatasetNotFoundError(str(dataset_path))

    metadata = read_yolo_data_yaml(dataset_path)
    class_names = metadata.get("names", [])
    if isinstance(class_names, dict):
        class_names = list(class_names.values())

    issue_counts: Counter[str] = Counter()
    issues: list[AnnotationIssue] = []
    total_images = 0

    for image_path, label_path in iter_yolo_labels(dataset_path):
        total_images += 1
        annotations = parse_yolo_label(label_path)
        if not annotations:
            issue_counts["empty_label_file"] += 1
            issues.append(
                AnnotationIssue(
                    check="empty_label_file",
                    file=label_path,
                    message="Label file exists but contains no valid annotations.",
                )
            )
            continue

        if len(annotations) > _MAX_OBJECTS_PER_IMAGE:
            issue_counts["crowded_image"] += 1
            issues.append(
                AnnotationIssue(
                    check="crowded_image",
                    file=image_path,
                    message=f"Image contains {len(annotations)} annotations.",
                )
            )

        xyxy_boxes = [_to_xyxy(annotation) for annotation in annotations]
        for index, (class_id, center_x, center_y, width, height) in enumerate(annotations):
            if class_id < 0 or class_id >= len(class_names):
                issue_counts["invalid_class_id"] += 1
                issues.append(
                    AnnotationIssue(
                        check="invalid_class_id",
                        file=label_path,
                        message=f"Annotation {index + 1} uses out-of-range class id {class_id}.",
                    )
                )
            if width <= 0 or height <= 0 or width * height < _SMALL_BOX_AREA:
                issue_counts["tiny_bbox"] += 1
                issues.append(
                    AnnotationIssue(
                        check="tiny_bbox",
                        file=label_path,
                        message=f"Annotation {index + 1} is too small to be reliable.",
                    )
                )
            if not (
                0 <= center_x <= 1 and 0 <= center_y <= 1 and 0 < width <= 1 and 0 < height <= 1
            ):
                issue_counts["bbox_out_of_bounds"] += 1
                issues.append(
                    AnnotationIssue(
                        check="bbox_out_of_bounds",
                        file=label_path,
                        message=f"Annotation {index + 1} falls outside normalized YOLO bounds.",
                    )
                )

        for left_index, left_box in enumerate(xyxy_boxes):
            for right_box in xyxy_boxes[left_index + 1 :]:
                if _bbox_iou(left_box, right_box) >= _OVERLAP_THRESHOLD:
                    issue_counts["overlapping_bbox"] += 1
                    issues.append(
                        AnnotationIssue(
                            check="overlapping_bbox",
                            file=label_path,
                            message="Two annotations overlap almost perfectly (IoU >= 0.9).",
                        )
                    )
                    break

    return AnnotationQualityCheckOutput(
        dataset_path=dataset_path,
        total_images=total_images,
        total_issue_count=sum(issue_counts.values()),
        issue_counts=dict(issue_counts),
        issues=issues[:100],
        warnings=[],
    )


def _to_xyxy(
    annotation: tuple[int, float, float, float, float],
) -> tuple[float, float, float, float]:
    _, center_x, center_y, width, height = annotation
    return (
        center_x - width / 2,
        center_y - height / 2,
        center_x + width / 2,
        center_y + height / 2,
    )


def _bbox_iou(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> float:
    ax1, ay1, ax2, ay2 = left
    bx1, by1, bx2, by2 = right
    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)
    inter_w = max(inter_x2 - inter_x1, 0.0)
    inter_h = max(inter_y2 - inter_y1, 0.0)
    intersection = inter_w * inter_h
    if intersection <= 0:
        return 0.0
    area_left = max(ax2 - ax1, 0.0) * max(ay2 - ay1, 0.0)
    area_right = max(bx2 - bx1, 0.0) * max(by2 - by1, 0.0)
    union = area_left + area_right - intersection
    return intersection / union if union > 0 else 0.0
