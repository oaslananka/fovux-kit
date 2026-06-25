"""Validate reproducible benchmark output contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    schema = _read(ROOT / "fovux-mcp" / "src" / "fovux" / "schemas" / "inference.py")
    for phrase in [
        "baseline_path",
        "num_warmup",
        "input_shape",
        "environment",
        "artifact",
        "comparison",
        "reproducibility_notes",
    ]:
        if phrase not in schema:
            failures.append(f"Benchmark schema missing {phrase}")
    tool = _read(
        ROOT / "fovux-mcp" / "src" / "fovux" / "tools" / "benchmark_latency.py"
    )
    for phrase in [
        "np.percentile",
        "sha256",
        "threshold_ratio",
        "Warmup iterations",
        "baseline_p95_ms",
    ]:
        if phrase not in tool:
            failures.append(f"benchmark_latency missing {phrase}")
    tests = _read(
        ROOT / "fovux-mcp" / "tests" / "unit" / "tools" / "test_benchmark_latency.py"
    )
    for phrase in [
        "reproducibility_context",
        "baseline.json",
        "input_shape",
        "comparison",
        "regression",
    ]:
        if phrase not in tests:
            failures.append(f"Benchmark tests missing {phrase}")
    docs = _read(ROOT / "docs" / "benchmark-reproducibility-contract.md")
    for phrase in ["p50", "p95", "SHA-256", "Baseline comparison", "10%"]:
        if phrase not in docs:
            failures.append(f"Benchmark docs missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Benchmark reproducibility checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
