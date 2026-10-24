"""Regressions for strict, frozen local backend vulnerability audits."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


class AuditEntryPointContractTests(unittest.TestCase):
    """Verify all local audit commands stay aligned with hosted CI."""

    def test_mcp_audit_uses_frozen_lock_and_strict_environment(self) -> None:
        root = Path(__file__).resolve().parents[3]
        spec = importlib.util.spec_from_file_location(
            "fovux_quality_gate_contract", root / "scripts" / "quality_gate.py"
        )
        self.assertIsNotNone(spec)
        if spec is None or spec.loader is None:
            self.fail("Could not load quality gate module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with patch.object(module, "_run") as run:
            module.mcp_audit()

        self.assertEqual(run.call_count, 3)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertEqual(commands[0], ["uv", "lock", "--check"])
        self.assertEqual(
            commands[1],
            [
                "uv",
                "export",
                "--frozen",
                "--no-dev",
                "--no-editable",
                "--no-emit-project",
                "--no-hashes",
                "--output-file",
                "requirements-audit.txt",
            ],
        )
        self.assertEqual(
            commands[2],
            [
                "uv",
                "run",
                "--frozen",
                "--no-build",
                "--no-sync",
                "pip-audit",
                "--requirement",
                "requirements-audit.txt",
                "--strict",
            ],
        )
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["cwd"], module.MCP_DIR)

    def test_taskfile_uses_identical_frozen_strict_audit_policy(self) -> None:
        taskfile = (Path(__file__).resolve().parents[3] / "Taskfile.yml").read_text()
        task = taskfile.split("  security:pip-audit:", 1)[1].split("  security:pnpm-audit:", 1)[0]
        self.assertIn(
            "uv export --frozen --no-dev --no-editable --no-emit-project",
            task,
        )
        self.assertIn(
            "uv run --frozen --no-build --no-sync pip-audit "
            "--requirement requirements-audit.txt --strict",
            task,
        )
