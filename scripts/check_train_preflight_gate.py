"""Validate train_preflight-first training workflow contracts."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    schema = _read(ROOT / "fovux-mcp" / "src" / "fovux" / "schemas" / "training.py")
    for phrase in [
        "ready",
        "blockers",
        "next_actions",
        "override_required",
        "override_hint",
    ]:
        if phrase not in schema:
            failures.append(f"TrainPreflightOutput missing {phrase}")
    tool = _read(ROOT / "fovux-mcp" / "src" / "fovux" / "tools" / "train_preflight.py")
    for phrase in [
        "Dataset check failed",
        "Model check failed",
        "Concurrency check failed",
        "Call train_start",
        "run train_preflight again",
    ]:
        if phrase not in tool:
            failures.append(f"train_preflight output contract missing phrase: {phrase}")
    launcher = _read(
        ROOT / "fovux-studio" / "src" / "webviews" / "trainingLauncher" / "main.tsx"
    )
    preflight_index = launcher.find('"train_preflight"')
    start_index = launcher.find('"train_start"')
    if preflight_index < 0 or start_index < 0 or preflight_index > start_index:
        failures.append(
            "Training launcher must call train_preflight before train_start"
        )
    for phrase in ["blockers", "next_actions", "preflight_approval_reason", "force"]:
        if phrase not in launcher:
            failures.append(
                f"Training launcher missing preflight gate phrase: {phrase}"
            )
    docs = _read(ROOT / "docs" / "agent-training-workflow.md")
    for phrase in [
        "train_preflight",
        "train_start",
        "ready",
        "blockers",
        "next_actions",
        "preflight_approval_reason",
    ]:
        if phrase not in docs:
            failures.append(f"Agent training docs missing phrase: {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Train preflight gate checks passed: schema, tool output, Studio flow, and docs are aligned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
