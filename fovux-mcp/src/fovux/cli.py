"""Fovux MCP CLI entry point."""

from __future__ import annotations

import sys
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from fovux import __version__
from fovux.core.auth import auth_token_path, rotate_auth_token, token_fingerprint
from fovux.core.doctor import collect_doctor_report
from fovux.core.logging import configure_logging, get_logger
from fovux.core.paths import get_fovux_home
from fovux.core.telemetry import set_telemetry, telemetry_status
from fovux.core.tool_registry import list_tool_names

app = typer.Typer(
    name="fovux-mcp",
    help="Fovux MCP — edge-AI computer vision workbench.",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()
logger = get_logger(__name__)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", help="Show version and exit."),
    log_level: str | None = typer.Option(None, "--log-level", help="Override FOVUX_LOG_LEVEL."),
    log_format: str | None = typer.Option(
        None,
        "--log-format",
        help="Override FOVUX_LOG_FORMAT (json or pretty).",
    ),
) -> None:
    """Start Fovux MCP server (stdio mode) when called without a subcommand."""
    configure_logging(level=log_level, fmt=log_format)
    ctx.obj = {"log_level": log_level, "log_format": log_format}
    if version:
        console.print(f"fovux-mcp {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        _run_stdio()


def _run_stdio() -> None:
    """Run MCP server in stdio mode (default for MCP clients)."""
    from fovux.server import mcp

    logger.info("stdio_server_start")
    mcp.run()


@app.command()
def serve(
    ctx: typer.Context,
    http: bool = typer.Option(False, "--http", help="Enable HTTP transport."),
    host: str = typer.Option("127.0.0.1", "--host", help="HTTP bind host."),
    port: int = typer.Option(7823, "--port", help="HTTP bind port."),
    tcp: bool = typer.Option(False, "--tcp", help="Force TCP instead of a Unix domain socket."),
    metrics: bool = typer.Option(False, "--metrics", help="Enable local Prometheus /metrics."),
) -> None:
    """Start the MCP server (stdio by default, or HTTP with --http)."""
    _configure_from_context(ctx.obj)
    if http:
        import uvicorn

        from fovux.http.app import create_app, warn_if_nonlocal_host

        warn_if_nonlocal_host(host)
        web_app = create_app(enable_metrics=metrics)
        if sys.platform != "win32" and not tcp:
            socket_path = get_fovux_home() / "fovux.sock"
            if socket_path.exists():
                socket_path.unlink()
            logger.info("http_server_start", socket=str(socket_path))
            config = uvicorn.Config(web_app, uds=str(socket_path), log_level="warning")
        else:
            logger.info("http_server_start", host=host, port=port)
            config = uvicorn.Config(web_app, host=host, port=port, log_level="warning")
        server = uvicorn.Server(config)
        server.run()
    else:
        _run_stdio()


@app.command()
def version() -> None:
    """Print version information."""
    console.print(f"fovux-mcp {__version__} ({len(list_tool_names())} tools)")


@app.command()
def doctor(ctx: typer.Context) -> None:
    """Check environment health and print a diagnostic report."""
    _configure_from_context(ctx.obj)
    report = collect_doctor_report()

    table = Table(title=f"Fovux MCP {__version__} — Environment Health")
    table.add_column("Check", style="bold")
    table.add_column("Status")
    table.add_column("Detail")

    rows = [
        ("Python version", True, report.python),
        ("GPU", report.gpu.available, f"{report.gpu.accelerator} · {report.gpu.detail}"),
        (
            "ultralytics",
            report.ultralytics.status == "ok",
            report.ultralytics.version or report.ultralytics.detail,
        ),
        (
            "onnxruntime",
            report.onnxruntime.status == "ok",
            report.onnxruntime.detail or (report.onnxruntime.version or "unknown"),
        ),
        ("onnx", report.onnx.status == "ok", report.onnx.version or report.onnx.detail),
        ("fastmcp", report.fastmcp.status == "ok", report.fastmcp.version or report.fastmcp.detail),
        (
            "FOVUX_HOME",
            report.fovux_home.writable,
            f"{report.fovux_home.path} · {report.fovux_home.disk_free_gb:.1f} GB free",
        ),
        ("HTTP transport", report.http.reachable, report.http.detail),
    ]
    all_ok = not report.errors
    for name, ok, detail in rows:
        status = "[green]OK[/green]" if ok else "[yellow]WARN[/yellow]"
        table.add_row(name, status, detail)

    console.print(table)
    if report.warnings:
        console.print("[yellow]Warnings:[/yellow]")
        for warning in report.warnings:
            console.print(f"- {warning}")
    if report.errors:
        console.print("[red]Errors:[/red]")
        for error in report.errors:
            console.print(f"- {error}")
    if not all_ok:
        raise typer.Exit(1)


@app.command("rotate-token")
def rotate_token_command(
    ctx: typer.Context,
    show_token: bool = typer.Option(
        False,
        "--show-token",
        help="Print the raw token once for manual local client configuration.",
    ),
) -> None:
    """Rotate the local HTTP bearer token used by the optional transport."""
    _configure_from_context(ctx.obj)
    token = rotate_auth_token()
    token_path = auth_token_path(get_fovux_home())
    console.print(f"Rotated token at {token_path}")
    console.print(f"Token fingerprint: {token_fingerprint(token)}")
    if show_token:
        console.print(token)
    else:
        console.print("Token value hidden. Use --show-token only for a one-time local reveal.")


telemetry_app = typer.Typer(help="Manage local-first telemetry settings.")
app.add_typer(telemetry_app, name="telemetry")


@telemetry_app.command("status")
def telemetry_status_command(ctx: typer.Context) -> None:
    """Print the effective telemetry configuration."""
    _configure_from_context(ctx.obj)
    status = telemetry_status()
    table = Table(title="Fovux Telemetry")
    table.add_column("Field", style="bold")
    table.add_column("Value")
    for key, value in status.items():
        table.add_row(str(key), str(value))
    console.print(table)


@telemetry_app.command("enable")
def telemetry_enable_command(
    ctx: typer.Context,
    endpoint: str = typer.Option(..., "--endpoint", help="Self-hosted telemetry endpoint URL."),
) -> None:
    """Enable opt-in telemetry to a user-controlled endpoint."""
    _configure_from_context(ctx.obj)
    status = set_telemetry(enabled=True, endpoint=endpoint)
    console.print("Telemetry enabled.")
    console.print(status)


@telemetry_app.command("disable")
def telemetry_disable_command(ctx: typer.Context) -> None:
    """Disable telemetry in config.toml."""
    _configure_from_context(ctx.obj)
    status = set_telemetry(enabled=False)
    console.print("Telemetry disabled.")
    console.print(status)


def _configure_from_context(options: object) -> None:
    if not isinstance(options, dict):
        configure_logging()
        return
    ctx_options = options
    configure_logging(
        level=_option_value(ctx_options, "log_level"),
        fmt=_option_value(ctx_options, "log_format"),
    )


def _option_value(options: dict[str, Any], key: str) -> str | None:
    value = options.get(key)
    return str(value) if value is not None else None


if __name__ == "__main__":
    app()
