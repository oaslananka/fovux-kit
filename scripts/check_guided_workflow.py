"""Validate the Fovux Studio guided workflow contract."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDIO = ROOT / "fovux-studio"
WORKFLOW = STUDIO / "src" / "fovux" / "guidedWorkflow.ts"
EXTENSION = STUDIO / "src" / "extension.ts"
PACKAGE = STUDIO / "package.json"
TSUP = STUDIO / "tsup.config.ts"
WEBVIEW = STUDIO / "src" / "webviews" / "guidedWorkflow" / "main.tsx"
COMMAND = STUDIO / "src" / "commands" / "openGuidedWorkflow.ts"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    failures: list[str] = []
    workflow = _read(WORKFLOW)
    stage_ids = re.findall(r'^    id: "([^"]+)"', workflow, flags=re.M)
    expected = [
        "discover_dataset",
        "validate_inspect",
        "prepare_dataset",
        "preflight_train",
        "monitor_evaluate",
        "export_deploy",
    ]
    if stage_ids != expected:
        failures.append(f"Guided workflow stage order mismatch: {stage_ids}")
    for phrase in [
        "mcpToolName",
        "cliCommand",
        "requiredInputs",
        "nextActions",
        "remediation",
        "offlineDemo",
        "demo_init",
        "dataset_validate",
        "train_preflight",
        "train_start",
        "eval_run",
        "export_onnx",
        "deployment_advise",
        "export_reproducibility_bundle",
    ]:
        if phrase not in workflow:
            failures.append(f"Guided workflow manifest missing phrase: {phrase}")
    for path, phrase in [
        (EXTENSION, "fovux.openGuidedWorkflow"),
        (PACKAGE, "fovux.openGuidedWorkflow"),
        (TSUP, "webviews/guidedWorkflow/main"),
        (WEBVIEW, "Fovux Guided Workflow"),
        (COMMAND, "openGuidedWorkflow"),
    ]:
        if phrase not in _read(path):
            failures.append(f"{path.relative_to(ROOT)} missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print(
        "Guided workflow checks passed: manifest, command, webview, package, and bundle entry are aligned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
