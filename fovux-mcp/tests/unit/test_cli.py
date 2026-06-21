"""Tests for CLI entry points and helper functions."""

from __future__ import annotations

import os
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


def test_run_stdio_invokes_mcp_server(monkeypatch) -> None:
    """The stdio helper should keep MCP stdout free of CLI chatter."""
    monkeypatch.setenv("FASTMCP_CHECK_FOR_UPDATES", "stable")
    with (
        patch("fovux.cli.logger") as logger,
        patch("fovux.server.mcp.run") as run_server,
    ):
        _run_stdio()

    assert os.environ["FASTMCP_CHECK_FOR_UPDATES"] == "off"
    logger.info.assert_called_once_with("stdio_server_start")
    run_server.assert_called_once_with(show_banner=False)


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
    assert "37 tools" in result.stdout


def test_doctor_success_prints_table(tmp_path: Path) -> None:
    """A healthy environment should produce a successful doctor report."""
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.collect_doctor_report", return_value=_doctor_report()),
        patch(
            "fovux.cli.check_token_perms",
            return_value=(True, "auth.token permissions are safe"),
        ),
    ):
        result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Environment Health" in result.stdout
    assert "FAIL" not in result.stdout


def test_doctor_failure_exits_nonzero(tmp_path: Path) -> None:
    """A failing doctor check should exit with status code 1."""
    with (
        patch("fovux.cli.configure_logging"),
        patch(
            "fovux.cli.collect_doctor_report",
            return_value=_doctor_report(errors=["Ultralytics is unavailable"]),
        ),
        patch(
            "fovux.cli.check_token_perms",
            return_value=(True, "auth.token permissions are safe"),
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
        patch("fovux.cli.check_token_perms", return_value=(True, "safe")),
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


def test_session_create_default_scopes(tmp_path: Path) -> None:
    """Creating a session token with default scopes should report fingerprint."""
    raw = "unit-test-session-raw"
    fp = token_fingerprint(raw)
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.get_fovux_home", return_value=tmp_path),
        patch("fovux.cli.create_session_token", return_value=raw),
    ):
        result = runner.invoke(app, ["session", "create"])

    assert result.exit_code == 0
    assert fp in result.stdout


def test_session_create_custom_scopes(tmp_path: Path) -> None:
    """Creating a session with custom scopes should show them in output."""
    raw = "unit-test-session-raw"
    fp = token_fingerprint(raw)
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.get_fovux_home", return_value=tmp_path),
        patch("fovux.cli.create_session_token", return_value=raw),
    ):
        result = runner.invoke(
            app,
            ["session", "create", "--scope", "read", "--scope", "run:start"],
        )

    assert result.exit_code == 0
    assert fp in result.stdout
    assert "read" in result.stdout
    assert "run:start" in result.stdout


def test_session_create_invalid_scope_fails(tmp_path: Path) -> None:
    """Creating a session with an unknown scope should exit with error."""
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.get_fovux_home", return_value=tmp_path),
    ):
        result = runner.invoke(app, ["session", "create", "--scope", "bogus"])

    assert result.exit_code == 1
    assert "Invalid scope" in result.stdout


def test_session_list_empty(tmp_path: Path) -> None:
    """Listing sessions with no tokens should print a message."""
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.get_fovux_home", return_value=tmp_path),
        patch("fovux.cli.list_session_fingerprints", return_value=[]),
    ):
        result = runner.invoke(app, ["session", "list"])

    assert result.exit_code == 0
    assert "No active session tokens" in result.stdout


def test_session_list_populated(tmp_path: Path) -> None:
    """Listing sessions with tokens should show a table."""
    entries = [
        {"fingerprint": "abc123", "scopes": ["read"]},
        {"fingerprint": "def456", "scopes": ["read", "run:start"]},
    ]
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.get_fovux_home", return_value=tmp_path),
        patch("fovux.cli.list_session_fingerprints", return_value=entries),
    ):
        result = runner.invoke(app, ["session", "list"])

    assert result.exit_code == 0
    assert "abc123" in result.stdout
    assert "def456" in result.stdout
    assert "Active Session Tokens" in result.stdout


def test_session_revoke_success(tmp_path: Path) -> None:
    """Revoking an existing token should print a success message."""
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.get_fovux_home", return_value=tmp_path),
        patch("fovux.cli.revoke_session_token", return_value=True),
    ):
        result = runner.invoke(app, ["session", "revoke", "some-token"])

    assert result.exit_code == 0
    assert "Session token revoked" in result.stdout


def test_session_revoke_not_found(tmp_path: Path) -> None:
    """Revoking a missing token should print a warning."""
    with (
        patch("fovux.cli.configure_logging"),
        patch("fovux.cli.get_fovux_home", return_value=tmp_path),
        patch("fovux.cli.revoke_session_token", return_value=False),
    ):
        result = runner.invoke(app, ["session", "revoke", "unknown-token"])

    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()
