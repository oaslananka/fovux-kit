"""Regressions for strict, frozen local backend vulnerability audits."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch


def test_mcp_audit_uses_frozen_lock_and_strict_offline_environment() -> None:
    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "fovux_quality_gate_contract", root / "scripts" / "quality_gate.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with patch.object(module, "_run") as run:
        module.mcp_audit()

    assert run.call_count == 3
    commands = [call.args[0] for call in run.call_args_list]
    assert commands[0] == ["uv", "lock", "--check"]
    assert commands[1] == [
        "uv",
        "export",
        "--frozen",
        "--no-dev",
        "--no-editable",
        "--no-emit-project",
        "--no-hashes",
        "--output-file",
        "requirements-audit.txt",
    ]
    assert commands[2] == [
        "uv",
        "run",
        "--frozen",
        "--no-build",
        "--no-sync",
        "pip-audit",
        "--requirement",
        "requirements-audit.txt",
        "--strict",
    ]
    assert all(call.kwargs["cwd"] == module.MCP_DIR for call in run.call_args_list)


def test_taskfile_uses_identical_frozen_strict_audit_policy() -> None:
    taskfile = (Path(__file__).resolve().parents[3] / "Taskfile.yml").read_text()
    task = taskfile.split("  security:pip-audit:", 1)[1].split(
        "  security:pnpm-audit:", 1
    )[0]
    assert "uv export --frozen --no-dev --no-editable --no-emit-project" in task
    assert (
        "uv run --frozen --no-build --no-sync pip-audit "
        "--requirement requirements-audit.txt --strict"
    ) in task
