"""dataset_validate — deep integrity check for a dataset."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fovux.core.dataset_utils import (
    detect_format,
    iter_yolo_labels,
    parse_yolo_label,
    read_yolo_data_yaml,
)
from fovux.core.errors import FovuxDatasetFormatError, FovuxDatasetNotFoundError
from fovux.core.tooling import tool_event
from fovux.core.validation import ensure_within_root, resolve_local_path, validate_file_size
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
    if fmt == "yolo":
        return _validate_yolo(path, inp)
    raise FovuxDatasetFormatError(
        (f"dataset_validate currently supports YOLO datasets only; received '{fmt}'."),
        hint="Convert the dataset to YOLO before running deep validation.",
    )


def _validate_yolo(path: Path, inp: DatasetValidateInput) -> DatasetValidateOutput:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    try:
        meta = read_yolo_data_yaml(path)
        nc: int = int(meta.get("nc", 0))
    except Exception:
        nc = 0
        warnings.append(
            ValidationIssue(file="data.yaml", severity="warning", message="Cannot parse data.yaml")
        )

    bad_image_paths: list[str] = []
    out_of_bounds_files: list[str] = []

    for img_path, label_path in iter_yolo_labels(path):
        if inp.check_image_readable and img_path.exists():
            try:
                from PIL import Image

                safe_img_path = ensure_within_root(img_path, path)
                validate_file_size(safe_img_path)
                with Image.open(safe_img_path) as im:
                    im.verify()
            except Exception as e:
                errors.append(
                    ValidationIssue(
                        file=str(img_path),
                        severity="error",
                        message=f"Image unreadable: {e}",
                    )
                )
                bad_image_paths.append(str(img_path))

        if not label_path.exists():
            if img_path.exists():
                warnings.append(
                    ValidationIssue(
                        file=str(img_path),
                        severity="warning",
                        message="Image has no corresponding label file",
                    )
                )
            continue

        safe_label_path = ensure_within_root(label_path, path)
        validate_file_size(safe_label_path)
        anns = parse_yolo_label(label_path)
        for line_no, (cls, cx, cy, w, h) in enumerate(anns, start=1):
            if inp.check_bbox_bounds:
                if not (
                    0.0 <= cx <= 1.0 and 0.0 <= cy <= 1.0 and 0.0 < w <= 1.0 and 0.0 < h <= 1.0
                ):
                    sev: Literal["error", "warning"] = "error" if inp.strict else "warning"
                    errors.append(
                        ValidationIssue(
                            file=str(label_path),
                            line=line_no,
                            severity=sev,
                            message=(
                                "Bbox out of [0,1] range: "
                                f"cx={cx:.4f} cy={cy:.4f} w={w:.4f} h={h:.4f}"
                            ),
                        )
                    )
                    out_of_bounds_files.append(str(label_path))

            if inp.check_class_id_range and nc > 0:
                if cls < 0 or cls >= nc:
                    errors.append(
                        ValidationIssue(
                            file=str(label_path),
                            line=line_no,
                            severity="error",
                            message=f"Class ID {cls} out of range [0, {nc - 1}]",
                        )
                    )

    valid = len(errors) == 0
    n_err = len(errors)
    n_warn = len(warnings)
    summary = f"{'PASS' if valid else 'FAIL'}: {n_err} error(s), {n_warn} warning(s)"

    remediation: str | None = None
    if out_of_bounds_files:
        remediation = (
            "# Clip bbox values to [0,1] for affected label files:\n"
            "import glob, pathlib\n"
            "for f in " + repr(list(set(out_of_bounds_files))[:5]) + ":\n"
            "    lines = pathlib.Path(f).read_text().splitlines()\n"
            "    fixed = []\n"
            "    for l in lines:\n"
            "        p = l.split(); c=p[0]; vals=[max(0,min(1,float(v))) for v in p[1:]]\n"
            "        fixed.append(c + ' ' + ' '.join(f'{v:.6f}' for v in vals))\n"
            "    pathlib.Path(f).write_text('\\n'.join(fixed))\n"
        )

    return DatasetValidateOutput(
        valid=valid,
        errors=errors,
        warnings=warnings,
        summary=summary,
        remediation_script=remediation,
    )
