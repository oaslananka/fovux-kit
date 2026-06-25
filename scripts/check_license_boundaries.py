"""Validate licensing and third-party boundary documentation."""

from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    for path in [ROOT / "LICENSE", ROOT / "NOTICE", ROOT / "fovux-mcp" / "NOTICE"]:
        if not path.exists():
            failures.append(f"Missing license notice file: {path.relative_to(ROOT)}")
    docs = _read(ROOT / "docs" / "licensing-boundaries.md")
    for phrase in [
        "Apache-2.0",
        "Ultralytics",
        "ONNX",
        "TensorRT",
        "CoreML",
        "OpenVINO",
        "TFLite",
        "NCNN",
        "RKNN",
        "W&B",
        "Hugging Face",
        "no-telemetry",
    ]:
        if phrase not in docs:
            failures.append(f"Licensing docs missing {phrase}")
    report_code = _read(ROOT / "fovux-mcp" / "src" / "fovux" / "core" / "doctor.py")
    for phrase in ["Ultralytics", "AGPL", "NOTICE"]:
        if phrase not in report_code:
            failures.append(f"Doctor license notice missing {phrase}")
    bundle = _read(ROOT / "fovux-mcp" / "src" / "fovux" / "tools" / "bundles.py")
    for phrase in ["package_versions", "Ultralytics"]:
        if phrase not in bundle:
            failures.append(f"Support bundle inventory missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("License boundary checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
