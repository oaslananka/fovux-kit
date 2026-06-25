"""Validate first-run onboarding, demo workspace, and health-check contracts."""
from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def main() -> int:
    failures: list[str] = []
    demo = _read(ROOT / "fovux-mcp" / "src" / "fovux" / "tools" / "demo_init.py")
    for phrase in ["sample_dataset", "data.yaml", "demo_run_01", "demo_model.onnx", "README.md"]:
        if phrase not in demo:
            failures.append(f"demo_init missing {phrase}")
    dashboard = _read(ROOT / "fovux-studio" / "src" / "commands" / "openDashboard.ts")
    for phrase in ["initializeDemoWorkspace", "demo_workspace", "startFovuxServer", "demo_init", "refreshViews"]:
        if phrase not in dashboard:
            failures.append(f"Studio demo flow missing {phrase}")
    report = _read(ROOT / "fovux-mcp" / "src" / "fovux" / "core" / "doctor.py")
    for phrase in ["python_supported", "fovux_home_writable", "disk_minimum_5gb"]:
        if phrase not in report:
            failures.append(f"Report check missing {phrase}")
    tests = _read(ROOT / "fovux-mcp" / "tests" / "unit" / "tools" / "test_demo_init.py")
    for phrase in ["sample_dataset", "demo_run_01", "demo_model.onnx", "public_wrapper"]:
        if phrase not in tests:
            failures.append(f"Demo tests missing {phrase}")
    docs = _read(ROOT / "docs" / "first-run-onboarding-contract.md")
    for phrase in ["network dependency", "demo_init", "guided workflow"]:
        if phrase not in docs:
            failures.append(f"Onboarding docs missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("First-run onboarding checks passed: Studio demo flow, demo_init workspace, health markers, tests, and docs are aligned.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
