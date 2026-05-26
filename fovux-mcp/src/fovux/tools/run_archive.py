"""run_archive — archive completed run directories to tar.gz."""

from __future__ import annotations

import tarfile
from pathlib import Path
from typing import Any

from fovux.core.errors import FovuxError, FovuxTrainingRunNotFoundError
from fovux.core.paths import ensure_fovux_dirs
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.core.validation import ensure_within_root
from fovux.schemas.management import RunArchiveInput, RunArchiveOutput
from fovux.server import mcp


@mcp.tool()
def run_archive(run_id: str, delete_original: bool = True) -> dict[str, Any]:
    """Archive a terminal run under FOVUX_HOME/archive."""
    inp = RunArchiveInput(run_id=run_id, delete_original=delete_original)
    with tool_event("run_archive", run_id=run_id):
        return _run_run_archive(inp).model_dump(mode="json")


def _run_run_archive(inp: RunArchiveInput) -> RunArchiveOutput:
    paths = ensure_fovux_dirs()
    registry = get_registry(paths.runs_db)
    record = registry.get_run(inp.run_id)
    if record is None:
        raise FovuxTrainingRunNotFoundError(inp.run_id)
    if str(record.status) == "running":
        raise FovuxError(f"Run '{inp.run_id}' is still running and cannot be archived.")

    run_dir = ensure_within_root(Path(record.run_path), paths.runs)
    archive_dir = ensure_within_root(paths.home / "archive", paths.home)
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = ensure_within_root(archive_dir / f"{inp.run_id}.tar.gz", archive_dir)
    archived_files = sum(1 for path in run_dir.rglob("*") if path.is_file())

    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(run_dir, arcname=inp.run_id)

    deleted = False
    if inp.delete_original:
        import shutil

        shutil.rmtree(run_dir)
        deleted = True

    registry.update_status(inp.run_id, "archived")
    registry.update_extra(inp.run_id, {"archive_path": str(archive_path)})
    return RunArchiveOutput(
        run_id=inp.run_id,
        archive_path=archive_path,
        archived_files=archived_files,
        deleted_original=deleted,
    )
