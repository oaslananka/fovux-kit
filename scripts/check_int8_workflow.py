"""Validate INT8 calibration, reporting, and target-specific guardrails."""

from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    q8 = _read(ROOT / "fovux-mcp" / "src" / "fovux" / "tools" / "quantize_int8.py")
    for phrase in [
        "calibration_dataset",
        "validate_calibration_dataset",
        "min_images",
        "int8=True",
        "data=",
    ]:
        if phrase not in q8:
            failures.append(f"quantize_int8 missing {phrase}")
    report = _read(
        ROOT / "fovux-mcp" / "src" / "fovux" / "tools" / "quantize_report.py"
    )
    for phrase in [
        "original_map50",
        "quantized_map50",
        "max_map50_drop",
        "regressed",
        "strict",
    ]:
        if phrase not in report:
            failures.append(f"quantize_report missing {phrase}")
    bench = _read(
        ROOT / "fovux-mcp" / "src" / "fovux" / "tools" / "benchmark_latency.py"
    )
    for phrase in ["latency_p95_ms", "throughput_fps", "comparison", "baseline_path"]:
        if phrase not in bench:
            failures.append(f"benchmark_latency missing {phrase}")
    targets = _read(
        ROOT / "fovux-studio" / "src" / "webviews" / "exportWizard" / "targets.ts"
    )
    for phrase in [
        "quantize",
        "raspberry_pi_5",
        "jetson_nano",
        "mobile_android",
        "tflite",
    ]:
        if phrase not in targets:
            failures.append(f"Studio export target missing {phrase}")
    docs = _read(ROOT / "docs" / "int8-calibration-workflow.md")
    for phrase in [
        "representative",
        "quantize_int8",
        "quantize_report",
        "benchmark_latency",
        "Accuracy drop",
        "Studio export targets",
    ]:
        if phrase not in docs:
            failures.append(f"INT8 docs missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("INT8 workflow checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
