"""Startup-budget, dispatcher, diagnostics, and lazy-registration tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from importlib.resources import files
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock, patch

from fovux import __version__

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SERVER_IMPORT_BUDGET_SECONDS = 20.0


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PACKAGE_ROOT / "src")
    env["FASTMCP_CHECK_FOR_UPDATES"] = "off"
    return env


def test_server_import_uses_manifest_without_importing_tool_implementations() -> None:
    """Server construction must not eagerly import implementation modules."""
    script = """
import json
import sys
import time
start = time.perf_counter()
from fovux.server import mcp
elapsed = time.perf_counter() - start
print(json.dumps({
    "elapsed": elapsed,
    "tool_modules": sorted(
        name for name in sys.modules if name.startswith("fovux.tools.")
    ),
    "tool_count": len(mcp._local_provider._components),
}))
"""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=PACKAGE_ROOT,
        env=_subprocess_env(),
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout.splitlines()[-1])
    assert payload["tool_modules"] == []
    assert payload["tool_count"] == 47
    assert payload["elapsed"] < SERVER_IMPORT_BUDGET_SECONDS


def test_runtime_manifest_is_packaged_with_all_tools() -> None:
    """The wheel package must contain the release-time lazy schema manifest."""
    manifest = files("fovux").joinpath("tool_manifest.json")
    payload = json.loads(manifest.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["tool_count"] == 47
    assert len(payload["tools"]) == 47


def test_console_scripts_use_fast_dispatcher() -> None:
    """Both public command aliases should use the no-argument stdio fast path."""
    pyproject = tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]

    assert scripts["fovux-mcp"] == "fovux.stdio:main"
    assert scripts["fovux"] == "fovux.stdio:main"


def test_stdio_dispatcher_preserves_cli_commands() -> None:
    """Supplying CLI arguments must retain the historical Typer command surface."""
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "fovux.stdio", "--version"],
        cwd=PACKAGE_ROOT,
        env=_subprocess_env(),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert f"fovux-mcp {__version__}" in result.stdout


def test_startup_diagnostics_are_opt_in_and_use_stderr() -> None:
    """Timing checkpoints must never contaminate MCP stdout."""
    script = "from fovux.startup import startup_checkpoint; startup_checkpoint('unit_test')"
    disabled = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=PACKAGE_ROOT,
        env=_subprocess_env(),
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    enabled_env = _subprocess_env()
    enabled_env["FOVUX_STARTUP_DIAGNOSTICS"] = "1"
    enabled = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        cwd=PACKAGE_ROOT,
        env=enabled_env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert disabled.returncode == 0
    assert disabled.stdout == ""
    assert disabled.stderr == ""
    assert enabled.returncode == 0
    assert enabled.stdout == ""
    record = json.loads(enabled.stderr)
    assert record["event"] == "fovux_startup"
    assert record["stage"] == "unit_test"
    assert record["elapsed_ms"] >= 0


def test_run_stdio_configures_logging_and_starts_server(monkeypatch) -> None:
    """The fast path must configure stderr logging before FastMCP registration logs."""
    from fovux.server import mcp
    from fovux.stdio import run_stdio

    monkeypatch.delenv("FASTMCP_CHECK_FOR_UPDATES", raising=False)
    with (
        patch("fovux.core.logging.configure_logging") as configure_logging,
        patch.object(mcp, "run") as run,
    ):
        run_stdio()

    configure_logging.assert_called_once_with()
    run.assert_called_once_with(show_banner=False)
    assert os.environ["FASTMCP_CHECK_FOR_UPDATES"] == "off"


def test_dispatcher_selects_fast_path_without_arguments(monkeypatch) -> None:
    """No-argument console invocation must avoid importing the interactive CLI."""
    from fovux.stdio import main

    monkeypatch.setattr(sys, "argv", ["fovux-mcp"])
    with patch("fovux.stdio.run_stdio") as run_stdio:
        main()

    run_stdio.assert_called_once_with()


def test_dispatcher_selects_cli_with_arguments(monkeypatch) -> None:
    """Any CLI argument must dispatch to the historical Typer application."""
    from fovux.stdio import main

    fake_cli = ModuleType("fovux.cli")
    fake_app = Mock()
    fake_cli.app = fake_app  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fovux.cli", fake_cli)
    monkeypatch.setattr(sys, "argv", ["fovux-mcp", "doctor"])

    main()

    fake_app.assert_called_once_with()
