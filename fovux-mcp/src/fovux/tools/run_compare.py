"""run_compare — compare multiple training runs and write a markdown report."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from PIL import Image, ImageDraw

from fovux.core.errors import FovuxTrainingRunNotFoundError
from fovux.core.paths import ensure_fovux_dirs, get_fovux_home
from fovux.core.runs import RunRegistry, get_registry
from fovux.core.tooling import tool_event
from fovux.core.validation import ensure_writable_output
from fovux.schemas.management import RunCompareInput, RunCompareOutput, RunMetricSummary
from fovux.server import mcp


@mcp.tool()
def run_compare(
    run_ids: list[str] | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Compare training runs on shared metrics and write markdown plus a PNG chart."""
    inp = RunCompareInput(
        run_ids=run_ids or [],
        output_path=Path(output_path) if output_path else None,
    )
    with tool_event("run_compare", run_ids=run_ids or [], output_path=output_path):
        return _run_run_compare(inp).model_dump(mode="json")


def _run_run_compare(inp: RunCompareInput) -> RunCompareOutput:
    paths = ensure_fovux_dirs(get_fovux_home())
    registry = get_registry(paths.runs_db)

    records = _select_records(registry, inp.run_ids)
    compared_runs: list[RunMetricSummary] = []
    for record in records:
        summary = _summarize_run(record)
        if summary is not None:
            compared_runs.append(summary)
    compared_runs.sort(
        key=lambda summary: summary.best_map50 if summary.best_map50 is not None else float("-inf"),
        reverse=True,
    )

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    base_dir = ensure_writable_output(inp.output_path or paths.exports / f"run_compare_{timestamp}")
    base_dir.mkdir(parents=True, exist_ok=True)
    report_path = base_dir / "report.md"
    chart_path = base_dir / "best_map50.png"

    _write_markdown_report(report_path, compared_runs)
    _write_chart(chart_path, compared_runs)

    best_run_id = compared_runs[0].run_id if compared_runs else None
    return RunCompareOutput(
        compared_runs=compared_runs,
        best_run_id=best_run_id,
        report_path=report_path,
        chart_path=chart_path,
    )


def _select_records(registry: RunRegistry, run_ids: list[str]) -> list[Any]:
    if not run_ids:
        return registry.list_runs(limit=1000)

    records = []
    for run_id in run_ids:
        record = registry.get_run(run_id)
        if record is None:
            raise FovuxTrainingRunNotFoundError(run_id)
        records.append(record)
    return records


def _summarize_run(record: object) -> RunMetricSummary | None:
    from fovux.tools.train_status import _read_metrics

    typed_record = cast(Any, record)
    run_path = Path(typed_record.run_path)
    current_epoch, best_map50 = _read_metrics(run_path)
    return RunMetricSummary(
        run_id=str(typed_record.id),
        status=str(typed_record.status),
        model=str(typed_record.model),
        epochs=int(typed_record.epochs),
        current_epoch=current_epoch,
        best_map50=best_map50,
        run_path=run_path,
    )


def _write_markdown_report(report_path: Path, runs: list[RunMetricSummary]) -> None:
    lines = [
        "# Fovux Run Compare",
        "",
        "| Run | Status | Model | Epochs | Current Epoch | Best mAP50 |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for run in runs:
        best_map50 = f"{run.best_map50:.4f}" if run.best_map50 is not None else "n/a"
        current_epoch = str(run.current_epoch) if run.current_epoch is not None else "n/a"
        lines.append(
            f"| {run.run_id} | {run.status} | {run.model} | {run.epochs} | "
            f"{current_epoch} | {best_map50} |"
        )
    if not runs:
        lines.append("| _no runs_ | - | - | - | - | - |")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def _write_chart(chart_path: Path, runs: list[RunMetricSummary]) -> None:
    width = 900
    row_height = 48
    height = max(120, 60 + row_height * max(1, len(runs)))
    image = Image.new("RGB", (width, height), color=(19, 23, 27))
    draw = ImageDraw.Draw(image)
    draw.text((24, 16), "Best mAP50 by run", fill=(240, 240, 240))

    max_value = max((run.best_map50 or 0.0) for run in runs) if runs else 1.0
    usable_width = width - 260

    for index, run in enumerate(runs):
        y = 56 + index * row_height
        value = run.best_map50 or 0.0
        bar_width = int((value / max_value) * usable_width) if max_value else 0
        draw.text((24, y), run.run_id, fill=(225, 225, 225))
        draw.rectangle((180, y + 4, 180 + bar_width, y + 28), fill=(255, 106, 61))
        draw.text((190 + bar_width, y + 6), f"{value:.4f}", fill=(225, 225, 225))

    image.save(chart_path)
