"""run_delete — remove a completed run from the registry and filesystem."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fovux.core.errors import FovuxTrainingError, FovuxTrainingRunNotFoundError
from fovux.core.paths import ensure_fovux_dirs, get_fovux_home
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.core.validation import ensure_within_root
from fovux.schemas.management import RunDeleteInput, RunDeleteOutput
from fovux.server import mcp


@mcp.tool()
def run_delete(
    run_id: str,
    delete_files: bool = True,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Delete a non-running training run and optionally remove its run directory."""
    inp = RunDeleteInput(run_id=run_id, delete_files=delete_files, force=force, dry_run=dry_run)
    with tool_event(
        "run_delete",
        run_id=run_id,
        delete_files=delete_files,
        force=force,
        dry_run=dry_run,
    ):
        return _run_delete(inp).model_dump(mode="json")


def _run_delete(inp: RunDeleteInput) -> RunDeleteOutput:
    paths = ensure_fovux_dirs(get_fovux_home())
    registry = get_registry(paths.runs_db)
    record = registry.get_run(inp.run_id)
    if record is None:
        raise FovuxTrainingRunNotFoundError(inp.run_id)

    if record.status == "running" and not inp.force:
        raise FovuxTrainingError(
            f"Run {inp.run_id} is still running.",
            hint="Stop the run first, or pass force=True if you are sure it is safe.",
        )

    deleted_files = False
    run_path_str = None
    affected_files_count = 0
    if inp.delete_files:
        run_path = ensure_within_root(Path(record.run_path), paths.runs)
        run_path_str = str(run_path)
        if run_path.exists():
            affected_files_count = sum(1 for p in run_path.rglob("*") if p.is_file())
            if not inp.dry_run:
                shutil.rmtree(run_path)
            deleted_files = True

    deleted_registry = False
    if not inp.dry_run:
        deleted_registry = registry.delete_run(inp.run_id)
    else:
        deleted_registry = True

    return RunDeleteOutput(
        run_id=inp.run_id,
        deleted_registry=deleted_registry,
        deleted_files=deleted_files,
        dry_run=inp.dry_run,
        run_path=run_path_str,
        affected_files_count=affected_files_count,
    )
