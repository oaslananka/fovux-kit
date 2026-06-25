"""Validate Studio dashboard resilience and comparison contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    dashboard = _read(
        ROOT / "fovux-studio" / "src" / "webviews" / "dashboard" / "main.tsx"
    )
    for phrase in [
        "polling fallback",
        "Malformed metric payloads are ignored",
        "readMetric",
        "MetricChart",
    ]:
        if phrase not in dashboard:
            failures.append(f"Dashboard missing resilience phrase: {phrase}")
    if "Backend disconnected" not in dashboard and not (
        "Backend " in dashboard and "disconnected:" in dashboard
    ):
        failures.append("Dashboard missing disconnected backend state")
    actions = _read(ROOT / "fovux-studio" / "src" / "commands" / "runActions.ts")
    for phrase in ["stopRun", "resumeRun", "deleteRun", "tagRun"]:
        if phrase not in actions:
            failures.append(f"Run action missing {phrase}")
    compare = _read(
        ROOT / "fovux-studio" / "src" / "webviews" / "compareRuns" / "main.tsx"
    )
    for phrase in [
        "best_map50",
        "config_diffs",
        "pareto_frontier_run_ids",
        "model_cards",
        "report_path",
    ]:
        if phrase not in compare:
            failures.append(f"Compare runs missing {phrase}")
    docs = _read(ROOT / "docs" / "dashboard-resilience-contract.md")
    for phrase in [
        "reconnecting/polling fallback",
        "Malformed metric payloads",
        "Run comparison",
    ]:
        if phrase not in docs:
            failures.append(f"Dashboard docs missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Dashboard resilience checks passed: fallback state, malformed metrics, run actions, comparison fields, and docs are aligned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
