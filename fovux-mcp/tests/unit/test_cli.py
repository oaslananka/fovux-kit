"""Tests for CLI entry points and helper functions."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from fovux import __version__
from fovux.cli import (
    _configure_from_context,
    _option_value,
    _run_stdio,
    app,
)
from fovux.core.auth import token_fingerprint
from fovux.schemas.diagnostics import (
    FovuxDoctorOutput,
    FovuxHomeHealth,
    GpuHealth,
    HttpHealth,
    PackageHealth,
)

runner = CliRunner()


def _doctor_report(*, errors: list[str] | None = None) -> FovuxDoctorOutput:
    return FovuxDoctorOutput(
        python="3.12.0",
        gpu=GpuHealth(available=True, accelerator="cuda", detail="CUDA is available"),
        ultralytics=PackageHealth(status="ok", version="8.4.0"),
        onnxruntime=PackageHealth(status="ok", version="1.24.0", detail="CPUExecutionProvider"),
        onnx=PackageHealth(status="ok", version="1.21.0"),
        fastmcp=PackageHealth(status="ok", version="3.2.0"),
        http=HttpHealth(
            reachable=True,
            base_url="http://127.0.0.1:7823/health",
            detail="TCP health check succeeded",
        ),
        fovux_home=FovuxHomeHealth(
            path=Path("C:/Users/example/.fovux"),
            writable=True,
            disk_free_gb=42.0,
            run_count=0,
            model_count=0,
        ),
        warnings=[],
        errors=errors or [],
    )


def test_version_flag_prints_version() -> None:
    """The root callback should print the package version and exit cleanly."""
    with patch("fovux.cli.configure_logging") as configure_logging:
        result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert f"fovux-mcp {__version__}" in result.stdout
    configure_logging.assert_called_once_with(level=None, fmt=None)


def test_default_invocation_runs_stdio_server() -> None:
    """Calling the CLI without a subcommand should enter stdio mode."""
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli._run_stdio") as run_stdio,
    ):
        result = runner.invoke(app, [])

    assert result.exit_code == 0
    run_stdio.assert_called_once()


def test_run_stdio_invokes_mcp_server() -> None:
    """The stdio helper should log startup and invoke the MCP runtime."""
    with (
        patch("fovux.cli.logger") as logger,
        patch("fovux.server.mcp.run") as run_server,
    ):
        _run_stdio()

    logger.info.assert_called_once_with("stdio_server_start")
    run_server.assert_called_once()


def test_serve_stdio_uses_context_logging() -> None:
    """The stdio serve path should re-apply log settings from the callback context."""
    with (
        patch("fovux.cli.configure_logging") as configure_logging,
        patch("fovux.cli._run_stdio") as run_stdio,
    ):
        result = runner.invoke(
            app,
            ["--log-level", "DEBUG", "--log-format", "json", "serve"],
        )

    assert result.exit_code == 0
    assert configure_logging.call_args_list[-1].kwargs == {"level": "DEBUG", "fmt": "json"}
    run_stdio.assert_called_once()


def test_serve_http_runs_uvicorn_server() -> None:
    """The HTTP serve path should construct and run a uvicorn server."""
    fake_server = MagicMock()
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.http.app.create_app", return_value="web-app"),
        patch("uvicorn.Config", return_value="config") as config_cls,
        patch("uvicorn.Server", return_value=fake_server) as server_cls,
    ):
        result = runner.invoke(
            app,
            ["serve", "--http", "--tcp", "--host", "127.0.0.1", "--port", "9000"],
        )

    assert result.exit_code == 0
    config_cls.assert_called_once_with(
        "web-app",
        host="127.0.0.1",
        port=9000,
        log_level="warning",
    )
    server_cls.assert_called_once_with("config")
    fake_server.run.assert_called_once()


def test_serve_http_defaults_to_unix_socket_on_unix(tmp_path) -> None:
    """Unix HTTP serving should use a local socket unless TCP is requested."""
    fake_server = MagicMock()
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.sys.platform", "linux"),
        patch("fovux.cli.get_fovux_home", return_value=tmp_path),
        patch("fovux.http.app.create_app", return_value="web-app"),
        patch("uvicorn.Config", return_value="config") as config_cls,
        patch("uvicorn.Server", return_value=fake_server) as server_cls,
    ):
        result = runner.invoke(app, ["serve", "--http"])

    assert result.exit_code == 0
    config_cls.assert_called_once_with(
        "web-app",
        uds=str(tmp_path / "fovux.sock"),
        log_level="warning",
    )
    server_cls.assert_called_once_with("config")
    fake_server.run.assert_called_once()


def test_version_command_prints_version() -> None:
    """The explicit version subcommand should print version and tool count."""
    with patch("fovux.cli.configure_logging"):
        result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert f"fovux-mcp {__version__}" in result.stdout
    assert "36 tools" in result.stdout


def test_doctor_success_prints_table() -> None:
    """A healthy environment should produce a successful doctor report."""
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.collect_doctor_report", return_value=_doctor_report()),
    ):
        result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Environment Health" in result.stdout
    assert "FAIL" not in result.stdout


def test_doctor_failure_exits_nonzero() -> None:
    """A failing doctor check should exit with status code 1."""
    with (
        patch("fovux.cli.configure_logging"),
        patch(
            "fovux.cli.collect_doctor_report",
            return_value=_doctor_report(errors=["Ultralytics is unavailable"]),
        ),
    ):
        result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "Ultralytics is unavailable" in result.stdout


def test_option_value_stringifies_values() -> None:
    """CLI option extraction should normalize values into strings."""
    assert _option_value({"log_level": "INFO"}, "log_level") == "INFO"
    assert _option_value({"port": 7823}, "port") == "7823"
    assert _option_value({}, "missing") is None


def test_configure_from_context_handles_missing_options() -> None:
    """Non-dict callback contexts should fall back to default logging configuration."""
    with patch("fovux.cli.configure_logging") as configure_logging:
        _configure_from_context(None)

    configure_logging.assert_called_once_with()


def test_configure_from_context_uses_context_values() -> None:
    """Dict callback contexts should pass log settings through to logging config."""
    with patch("fovux.cli.configure_logging") as configure_logging:
        _configure_from_context({"log_level": "WARNING", "log_format": "pretty"})

    configure_logging.assert_called_once_with(level="WARNING", fmt="pretty")


def test_doctor_uses_shared_report() -> None:
    """The doctor command should delegate diagnostics to the shared core helper."""
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.collect_doctor_report", return_value=_doctor_report()) as collect,
    ):
        result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    collect.assert_called_once_with()


def test_rotate_token_hides_raw_token_by_default(tmp_path: Path) -> None:
    """Token rotation should not print the raw bearer token unless explicitly requested."""
    sample_value = "unit-test-redaction-value"
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.get_fovux_home", return_value=tmp_path),
        patch("fovux.cli.rotate_auth_token", return_value=sample_value),
    ):
        result = runner.invoke(app, ["rotate-token"])

    assert result.exit_code == 0
    assert sample_value not in result.stdout
    assert token_fingerprint(sample_value) in result.stdout
    assert "--show-token" in result.stdout


def test_rotate_token_show_token_opt_in_reveals_raw_token(tmp_path: Path) -> None:
    """The explicit reveal flag should support manual local client setup."""
    sample_value = "unit-test-redaction-value"
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.get_fovux_home", return_value=tmp_path),
        patch("fovux.cli.rotate_auth_token", return_value=sample_value),
    ):
        result = runner.invoke(app, ["rotate-token", "--show-token"])

    assert result.exit_code == 0
    assert sample_value in result.stdout
