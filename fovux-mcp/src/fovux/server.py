"""Fovux MCP server bootstrap.

Initializes a FastMCP server instance and registers the tool registry.
"""

from __future__ import annotations

from fastmcp import FastMCP

from fovux import __version__
from fovux.core.tool_registry import register_all

mcp: FastMCP = FastMCP(
    name="fovux",
    version=__version__,
    instructions=(
        "Fovux is an edge-AI computer vision workbench. "
        "Use these tools to inspect datasets, train YOLO models, evaluate checkpoints, "
        "export to ONNX/TFLite, quantize, benchmark latency, and run live RTSP inference. "
        "All operations are local — nothing leaves your machine."
    ),
)
register_all()
