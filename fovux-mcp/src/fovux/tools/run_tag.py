"""run_tag — replace user-facing tags for a training run."""

from __future__ import annotations

from typing import Any

from fovux.core.errors import FovuxTrainingRunNotFoundError
from fovux.core.paths import ensure_fovux_dirs, get_fovux_home
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.schemas.management import RunTagInput, RunTagOutput
from fovux.server import mcp


@mcp.tool()
def run_tag(run_id: str, tags: list[str] | None = None) -> dict[str, Any]:
    """Replace tags on a run for filtering and Studio organization."""
    inp = RunTagInput(run_id=run_id, tags=tags or [])
    with tool_event("run_tag", run_id=run_id, tags=inp.tags):
        return _run_tag(inp).model_dump(mode="json")


def _run_tag(inp: RunTagInput) -> RunTagOutput:
    paths = ensure_fovux_dirs(get_fovux_home())
    registry = get_registry(paths.runs_db)
    if registry.get_run(inp.run_id) is None:
        raise FovuxTrainingRunNotFoundError(inp.run_id)
    registry.update_tags(inp.run_id, _normalize_tags(inp.tags))
    return RunTagOutput(run_id=inp.run_id, tags=_normalize_tags(inp.tags))


def _normalize_tags(tags: list[str]) -> list[str]:
    """Trim, deduplicate, and sort tags."""
    return sorted({tag.strip() for tag in tags if tag.strip()})
