"""dataset_validate — deep integrity check for a normalized dataset inventory."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fovux.core.dataset_inventory import (
    AnnotationRecord,
    DatasetFinding,
    DatasetInventory,
    build_dataset_inventory,
)
from fovux.core.dataset_utils import detect_format
from fovux.core.errors import FovuxDatasetFormatError, FovuxDatasetNotFoundError
from fovux.core.tooling import tool_event
from fovux.core.validation import resolve_local_path
from fovux.schemas.dataset import (
    DatasetValidateInput,
    DatasetValidateOutput,
    ValidationIssue,
)
from fovux.server import mcp


@mcp.tool()
def dataset_validate(
    dataset_path: str,
    format: str = "auto",
    check_image_readable: bool = True,
    check_bbox_bounds: bool = True,
    check_class_id_range: bool = True,
    strict: bool = False,
) -> dict[str, Any]:
    """Deep integrity check: readable images, bbox bounds [0,1], class ID range, orphans.

    Returns a list of errors/warnings and an optional bash remediation script.
    """
    inp = DatasetValidateInput(
        dataset_path=Path(dataset_path),
        format=format,  # type: ignore[arg-type]
        check_image_readable=check_image_readable,
        check_bbox_bounds=check_bbox_bounds,
        check_class_id_range=check_class_id_range,
        strict=strict,
    )
    with tool_event(
        "dataset_validate",
        dataset_path=dataset_path,
        format=format,
        strict=strict,
    ):
        return _run_validate(inp).model_dump(mode="json")


def _run_validate(inp: DatasetValidateInput) -> DatasetValidateOutput:
    path = resolve_local_path(inp.dataset_path)
    if not path.exists():
        raise FovuxDatasetNotFoundError(str(path))

    fmt = inp.format if inp.format != "auto" else detect_format(path)
    if fmt not in {"yolo", "coco"}:
        raise FovuxDatasetFormatError(
            f"dataset_validate currently supports YOLO and COCO datasets; received '{fmt}'.",
            hint="Convert the dataset to YOLO or COCO before running deep validation.",
        )
    inventory = build_dataset_inventory(
        path,
        fmt,
        analyze_images=inp.check_image_readable,
        compute_fingerprints=False,
    )
    return _validate_inventory(inventory, inp)


def _validate_inventory(
    inventory: DatasetInventory,
    inp: DatasetValidateInput,
) -> DatasetValidateOutput:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    out_of_bounds_files: list[str] = []

    for finding in inventory.findings:
        issue = _issue_from_finding(finding)
        if finding.severity == "error":
            errors.append(issue)
        else:
            warnings.append(issue)

    for image_path in inventory.missing_annotation_images:
        warnings.append(
            ValidationIssue(
                file=str(image_path),
                severity="warning",
                message="Image has no corresponding label file",
            )
        )

    if inp.check_image_readable:
        for image in inventory.images:
            if image.analyzed and image.readable is False:
                detail = image.analysis_error or "unknown image decoding error"
                errors.append(
                    ValidationIssue(
                        file=str(image.path),
                        severity="error",
                        message=f"Image unreadable: {detail}",
                    )
                )

    for annotation in inventory.annotations:
        if inp.check_bbox_bounds and annotation.bbox is not None:
            if not annotation.bbox.is_within_bounds:
                severity: Literal["error", "warning"] = "error" if inp.strict else "warning"
                errors.append(
                    ValidationIssue(
                        file=str(annotation.source_path),
                        line=annotation.line,
                        severity=severity,
                        message=_bbox_bounds_message(annotation),
                    )
                )
                out_of_bounds_files.append(str(annotation.source_path))

        if inp.check_class_id_range and not _class_id_is_valid(inventory, annotation.class_id):
            errors.append(
                ValidationIssue(
                    file=str(annotation.source_path),
                    line=annotation.line,
                    severity="error",
                    message=_class_range_message(inventory, annotation.class_id),
                )
            )

    valid = len(errors) == 0
    summary = f"{'PASS' if valid else 'FAIL'}: {len(errors)} error(s), {len(warnings)} warning(s)"
    return DatasetValidateOutput(
        valid=valid,
        errors=errors,
        warnings=warnings,
        summary=summary,
        remediation_script=_build_bbox_remediation(out_of_bounds_files, inventory.format),
    )


def _issue_from_finding(finding: DatasetFinding) -> ValidationIssue:
    return ValidationIssue(
        file=str(finding.file),
        line=finding.line,
        severity=finding.severity,
        message=finding.message,
    )


def _bbox_bounds_message(annotation: AnnotationRecord) -> str:
    if annotation.bbox is None:
        return "Bbox cannot be normalized because image dimensions are missing"
    box = annotation.bbox
    return (
        "Bbox out of [0,1] range: "
        f"x_min={box.x_min:.4f} y_min={box.y_min:.4f} "
        f"x_max={box.x_max:.4f} y_max={box.y_max:.4f}"
    )


def _class_id_is_valid(inventory: DatasetInventory, class_id: int) -> bool:
    if inventory.format == "yolo" and inventory.declared_class_count:
        return 0 <= class_id < inventory.declared_class_count
    if inventory.class_names:
        return class_id in inventory.class_names
    return True


def _class_range_message(inventory: DatasetInventory, class_id: int) -> str:
    if inventory.format == "yolo" and inventory.declared_class_count:
        return f"Class ID {class_id} out of range [0, {inventory.declared_class_count - 1}]"
    return f"Class ID {class_id} is not declared in COCO categories"


def _build_bbox_remediation(
    out_of_bounds_files: list[str],
    dataset_format: str,
) -> str | None:
    if dataset_format != "yolo" or not out_of_bounds_files:
        return None
    unique_files = list(dict.fromkeys(out_of_bounds_files))[:5]
    return (
        "# Clip bbox values to [0,1] for affected label files:\n"
        "import pathlib\n"
        "for f in " + repr(unique_files) + ":\n"
        "    lines = pathlib.Path(f).read_text().splitlines()\n"
        "    fixed = []\n"
        "    for l in lines:\n"
        "        p = l.split(); c=p[0]; vals=[max(0,min(1,float(v))) for v in p[1:]]\n"
        "        fixed.append(c + ' ' + ' '.join(f'{v:.6f}' for v in vals))\n"
        "    pathlib.Path(f).write_text('\\n'.join(fixed))\n"
    )
