"""Regenerate README tool inventory tables from the central registry."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MCP_ROOT = ROOT / "fovux-mcp"
SRC = MCP_ROOT / "src"
START = "<!-- fovux-tools:start -->"
END = "<!-- fovux-tools:end -->"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fovux.core.tool_registry import list_tool_names  # noqa: E402

DESCRIPTIONS: dict[str, str] = {
    "annotation_quality_check": "Find common YOLO annotation quality issues.",
    "benchmark_latency": "Measure p50/p95/p99 inference latency.",
    "dataset_convert": "Convert datasets between supported formats.",
    "dataset_find_duplicates": "Detect duplicate images with perceptual hashing.",
    "dataset_inspect": "Inspect dataset structure, classes, and samples.",
    "dataset_split": "Create train/val/test splits.",
    "dataset_validate": "Validate dataset integrity and label ranges.",
    "eval_compare": "Compare evaluation outputs.",
    "eval_error_analysis": "Extract worst false-positive and false-negative samples.",
    "eval_per_class": "Report per-class validation metrics.",
    "eval_run": "Run validation for a checkpoint.",
    "export_onnx": "Export checkpoints to ONNX.",
    "export_tflite": "Export checkpoints to TFLite.",
    "fovux_doctor": "Report local environment health.",
    "infer_batch": "Run batch inference over image folders.",
    "infer_image": "Run single-image inference.",
    "infer_rtsp": "Run live RTSP inference with reconnect handling.",
    "model_list": "List local checkpoints and exports.",
    "model_profile": "Profile model size and complexity.",
    "quantize_int8": "Create INT8 quantized artifacts.",
    "quantize_report": "Compare quantized model quality.",
    "run_compare": "Compare local training runs.",
    "run_delete": "Delete non-running runs safely.",
    "run_tag": "Edit local run tags.",
    "train_resume": "Resume a stopped or failed run.",
    "train_start": "Start detached YOLO training.",
    "train_status": "Read current run status and metrics.",
    "train_stop": "Stop a running training process.",
}


def render_table() -> str:
    """Render the Markdown table for all registered tools."""
    rows = ["| Tool | Purpose |", "|---|---|"]
    for name in list_tool_names():
        rows.append(f"| `{name}` | {DESCRIPTIONS[name]} |")
    return "\n".join(rows)


def replace_block(path: Path, table: str) -> None:
    """Replace the generated table block in a Markdown document."""
    text = path.read_text(encoding="utf-8")
    if START not in text or END not in text:
        raise SystemExit(f"{path} is missing {START}/{END} markers")
    before, rest = text.split(START, maxsplit=1)
    _, after = rest.split(END, maxsplit=1)
    path.write_text(f"{before}{START}\n{table}\n{END}{after}", encoding="utf-8")


def main() -> None:
    """Regenerate tool tables in the root and MCP READMEs."""
    table = render_table()
    replace_block(ROOT / "README.md", table)
    replace_block(MCP_ROOT / "README.md", table)


if __name__ == "__main__":
    main()
