"""Enforce a focused mutmut CI score and exception budget."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

COUNT_KEYS = (
    "killed",
    "survived",
    "total",
    "no_tests",
    "skipped",
    "suspicious",
    "timeout",
    "segfault",
)


def _count(stats: Mapping[str, object], key: str) -> int:
    value = stats.get(key, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Mutation statistic {key!r} must be a non-negative integer")
    return value


def evaluate_stats(
    stats: Mapping[str, object],
    *,
    minimum_score: float,
    max_survived: int,
    max_timeouts: int,
) -> tuple[dict[str, int | float], list[str]]:
    """Return normalized summary values and policy failures."""
    counts = {key: _count(stats, key) for key in COUNT_KEYS}
    evaluated = sum(
        counts[key] for key in ("killed", "survived", "suspicious", "timeout", "segfault")
    )
    score = (counts["killed"] / evaluated * 100.0) if evaluated else 0.0
    summary: dict[str, int | float] = {**counts, "evaluated": evaluated, "score": score}

    failures: list[str] = []
    if evaluated == 0:
        failures.append("No mutants were evaluated; the mutation gate cannot pass.")
    if score < minimum_score:
        failures.append(f"Mutation score {score:.2f}% is below the required {minimum_score:.2f}%.")
    if counts["survived"] > max_survived:
        failures.append(
            f"{counts['survived']} mutants survived; the allowed maximum is {max_survived}."
        )
    if counts["timeout"] > max_timeouts:
        failures.append(
            f"{counts['timeout']} mutants timed out; the allowed maximum is {max_timeouts}."
        )
    if counts["no_tests"]:
        failures.append(f"{counts['no_tests']} mutants have no test coverage.")
    if counts["suspicious"]:
        failures.append(f"{counts['suspicious']} mutants have suspicious timing results.")
    if counts["segfault"]:
        failures.append(f"{counts['segfault']} mutants caused a segmentation fault.")
    if stats.get("check_was_interrupted_by_user") is True:
        failures.append("The mutation run was interrupted before completion.")
    return summary, failures


def render_summary(summary: Mapping[str, int | float], failures: list[str]) -> str:
    """Render a durable Markdown mutation report."""
    lines = [
        "# Mutation Testing Summary",
        "",
        f"- Mutation score: **{float(summary['score']):.2f}%**",
        f"- Evaluated mutants: **{int(summary['evaluated'])}**",
        f"- Killed: **{int(summary['killed'])}**",
        f"- Survived: **{int(summary['survived'])}**",
        f"- Timeout: **{int(summary['timeout'])}**",
        f"- Suspicious: **{int(summary['suspicious'])}**",
        f"- No tests: **{int(summary['no_tests'])}**",
        f"- Skipped: **{int(summary['skipped'])}**",
        f"- Segfault: **{int(summary['segfault'])}**",
        "",
        "## Gate Result",
        "",
    ]
    if failures:
        lines.extend(["**Failed**", "", *[f"- {failure}" for failure in failures]])
    else:
        lines.append("**Passed**")
    return "\n".join(lines) + "\n"


def _load_stats(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Mutation stats must contain a JSON object")
    return value


def main() -> int:
    """Load mutmut CI stats, write a Markdown report, and enforce thresholds."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stats", type=Path)
    parser.add_argument("--minimum-score", type=float, required=True)
    parser.add_argument("--max-survived", type=int, required=True)
    parser.add_argument("--max-timeouts", type=int, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    args = parser.parse_args()

    try:
        stats = _load_stats(args.stats)
        summary, failures = evaluate_stats(
            stats,
            minimum_score=args.minimum_score,
            max_survived=args.max_survived,
            max_timeouts=args.max_timeouts,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    report = render_summary(summary, failures)
    args.summary_output.write_text(report, encoding="utf-8")
    print(report, end="")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
