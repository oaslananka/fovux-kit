"""Verify local coverage of deterministic credential-free required CI gates."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TASKFILE = ROOT / "Taskfile.yml"
MANIFEST = ROOT / "required-local-gates.json"
_TASK_DEF_RE = re.compile(r"^  ([A-Za-z0-9:_-]+):\s*$", re.MULTILINE)
_TASK_CALL_RE = re.compile(r"^\s+- task:\s*([A-Za-z0-9:_-]+)\s*$", re.MULTILINE)
_JOB_DEF_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$", re.MULTILINE)
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]+")


def _blocks(text: str, pattern: re.Pattern[str]) -> dict[str, str]:
    matches = list(pattern.finditer(text))
    return {
        match.group(1): text[match.start() : matches[index + 1].start()]
        if index + 1 < len(matches)
        else text[match.start() :]
        for index, match in enumerate(matches)
    }


def _task_calls(taskfile_text: str) -> dict[str, set[str]]:
    return {
        name: set(_TASK_CALL_RE.findall(block))
        for name, block in _blocks(taskfile_text, _TASK_DEF_RE).items()
    }


def _reachable_tasks(tasks: Mapping[str, set[str]], start: str) -> set[str]:
    reachable: set[str] = set()
    pending = [start]
    while pending:
        task = pending.pop()
        if task in reachable:
            continue
        reachable.add(task)
        pending.extend(tasks.get(task, set()) - reachable)
    return reachable


def _aggregate_needs(workflow_text: str, aggregate_job: str) -> set[str]:
    jobs = _blocks(workflow_text, _JOB_DEF_RE)
    try:
        block = jobs[aggregate_job]
    except KeyError as exc:
        raise ValueError(f"workflow has no aggregate job {aggregate_job}") from exc
    match = re.search(
        r"^    needs:\s*(.*?)(?=^    (?:if|runs-on|permissions|timeout-minutes|steps):)",
        block,
        flags=re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise ValueError(f"aggregate job {aggregate_job} has no needs declaration")
    return {
        token for token in _TOKEN_RE.findall(match.group(1)) if token not in {"needs"}
    }


def _as_mapping(value: object, *, label: str, failures: list[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        failures.append(f"{label} must be an object")
        return {}
    return value


def validate_paths(*, root: Path, taskfile: Path, manifest_path: Path) -> list[str]:
    """Validate one manifest against workflows and the Taskfile call graph."""
    failures: list[str] = []
    try:
        manifest_raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"Cannot read {manifest_path}: {exc}"]
    manifest = _as_mapping(manifest_raw, label="manifest", failures=failures)

    try:
        taskfile_text = taskfile.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"Cannot read {taskfile}: {exc}"]
    tasks = _task_calls(taskfile_text)
    aggregate_task = manifest.get("aggregate_task")
    if not isinstance(aggregate_task, str) or not aggregate_task:
        failures.append("manifest aggregate_task must be a non-empty string")
        aggregate_task = ""
    elif aggregate_task not in tasks:
        failures.append(f"aggregate task {aggregate_task} is missing from Taskfile.yml")
    reachable = _reachable_tasks(tasks, aggregate_task) if aggregate_task else set()

    workflows = _as_mapping(
        manifest.get("workflows"), label="manifest workflows", failures=failures
    )
    for relative_path, config_raw in workflows.items():
        if not isinstance(relative_path, str):
            failures.append("workflow path keys must be strings")
            continue
        config = _as_mapping(
            config_raw, label=f"workflow config {relative_path}", failures=failures
        )
        aggregate_job = config.get("aggregate_job")
        if not isinstance(aggregate_job, str) or not aggregate_job:
            failures.append(f"{relative_path} aggregate_job must be a non-empty string")
            continue
        job_config = _as_mapping(
            config.get("jobs"), label=f"{relative_path} jobs", failures=failures
        )
        workflow_path = root / relative_path
        try:
            actual_jobs = _aggregate_needs(
                workflow_path.read_text(encoding="utf-8"), aggregate_job
            )
        except (OSError, ValueError) as exc:
            failures.append(f"Cannot inspect {relative_path}: {exc}")
            continue
        configured_jobs = set(job_config)
        missing = actual_jobs - configured_jobs
        stale = configured_jobs - actual_jobs
        for job in sorted(missing):
            failures.append(
                f"{relative_path} required job {job} is missing from the local gate manifest"
            )
        for job in sorted(stale):
            failures.append(
                f"{relative_path} manifest job {job} is not required by {aggregate_job}"
            )

        for job, entry_raw in job_config.items():
            entry = _as_mapping(
                entry_raw, label=f"{relative_path} job {job}", failures=failures
            )
            mode = entry.get("mode")
            if mode == "local":
                task = entry.get("task")
                if not isinstance(task, str) or not task:
                    failures.append(f"{relative_path} local job {job} requires a task")
                elif task not in tasks:
                    failures.append(
                        f"{relative_path} local job {job} maps to missing task {task}"
                    )
                elif task not in reachable:
                    failures.append(
                        f"local task {task} for {job} is not reachable from {aggregate_task}"
                    )
            elif mode == "hosted-only":
                reason = entry.get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    failures.append(
                        f"{relative_path} hosted-only job {job} requires a reason"
                    )
            else:
                failures.append(
                    f"{relative_path} job {job} has unsupported mode {mode!r}"
                )

    hosted_contexts = _as_mapping(
        manifest.get("hosted_required_contexts"),
        label="hosted_required_contexts",
        failures=failures,
    )
    for context, reason in hosted_contexts.items():
        if (
            not isinstance(context, str)
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            failures.append(f"hosted required context {context!r} requires a reason")

    return failures


def validate_repository(root: Path = ROOT) -> list[str]:
    """Validate the repository-owned local gate parity contract."""
    return validate_paths(
        root=root,
        taskfile=root / TASKFILE.name,
        manifest_path=root / MANIFEST.name,
    )


def main() -> int:
    """Run the local required-gate drift check."""
    failures = validate_repository()
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        print("Update required-local-gates.json and Taskfile.yml together.")
        return 1
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    workflow_count = len(manifest["workflows"])
    job_count = sum(len(config["jobs"]) for config in manifest["workflows"].values())
    print(
        "Required local gate parity passed: "
        f"{job_count} jobs across {workflow_count} aggregate workflows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
