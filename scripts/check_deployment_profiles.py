"""Validate deployment advice profile coverage."""

from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    docs = _read(ROOT / "docs" / "deployment-advise-profiles.md")
    for phrase in [
        "Jetson",
        "Raspberry Pi",
        "Apple Silicon",
        "OpenVINO",
        "Edge TPU",
        "NCNN",
        "Browser",
        "Generic CPU",
    ]:
        if phrase not in docs:
            failures.append(f"Deployment profile docs missing {phrase}")
    for phrase in [
        "export format",
        "quantization",
        "validation command",
        "benchmark command",
        "caveats",
    ]:
        if phrase not in docs:
            failures.append(f"Deployment advice docs missing {phrase}")
    tool = _read(
        ROOT / "fovux-mcp" / "src" / "fovux" / "tools" / "deployment_advise.py"
    )
    for phrase in [
        "compatibility_preflight",
        "quantization_recommendation",
        "readiness_score",
        "runtime_snippets",
        "risk_warnings",
    ]:
        if phrase not in tool:
            failures.append(f"deployment_advise missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Deployment profile checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
