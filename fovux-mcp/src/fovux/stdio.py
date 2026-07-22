"""Fast default entry point for stdio MCP clients with CLI fallback."""

from __future__ import annotations

import os
import sys

from fovux.startup import startup_checkpoint


def run_stdio() -> None:
    """Run the MCP server without importing the interactive Typer/Rich CLI."""
    os.environ["FASTMCP_CHECK_FOR_UPDATES"] = "off"
    from fovux.core.logging import configure_logging

    configure_logging()
    startup_checkpoint("stdio_entrypoint")
    from fovux.server import mcp

    startup_checkpoint("server_import_complete")
    mcp.run(show_banner=False)


def main() -> None:
    """Use the lightweight server path when no CLI arguments were supplied."""
    if len(sys.argv) == 1:
        run_stdio()
        return
    startup_checkpoint("cli_dispatch", argv=sys.argv[1:])
    from fovux.cli import app

    app()


if __name__ == "__main__":
    main()
