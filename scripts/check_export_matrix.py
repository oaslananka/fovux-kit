"""Validate export target matrix coverage."""

from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    docs = _read(ROOT / "docs" / "export-target-matrix.md")
    for phrase in ["ONNX", "TensorRT", "CoreML", "OpenVINO", "TFLite", "NCNN", "RKNN"]:
        if phrase not in docs:
            failures.append(f"Export matrix missing {phrase}")
    for phrase in [
        "export_onnx",
        "export_tflite",
        "quantize_int8",
        "planned/manual",
        "docs.ultralytics.com/modes/export",
    ]:
        if phrase not in docs:
            failures.append(f"Export matrix missing {phrase}")
    tool_dir = ROOT / "fovux-mcp" / "src" / "fovux" / "tools"
    for filename in ["export_onnx.py", "export_tflite.py", "quantize_int8.py"]:
        if not (tool_dir / filename).exists():
            failures.append(f"Missing export tool surface: {filename}")
    targets = _read(
        ROOT / "fovux-studio" / "src" / "webviews" / "exportWizard" / "targets.ts"
    )
    for phrase in [
        "desktop_tensorrt",
        "raspberry_pi_5",
        "jetson_nano",
        "onnx",
        "tflite",
    ]:
        if phrase not in targets:
            failures.append(f"Studio export target missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Export matrix checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
