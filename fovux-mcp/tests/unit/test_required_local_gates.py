from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_required_local_gates.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_required_local_gates", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    workflow = tmp_path / "workflow.yml"
    workflow.write_text(
        """jobs:
  scan:
    runs-on: ubuntu-latest
  hosted:
    runs-on: ubuntu-latest
  required:
    needs: [scan, hosted]
    runs-on: ubuntu-latest
""",
        encoding="utf-8",
    )
    taskfile = tmp_path / "Taskfile.yml"
    taskfile.write_text(
        """version: "3"
tasks:
  scan:
    cmds:
      - echo scan
  verify:required:
    cmds:
      - task: scan
""",
        encoding="utf-8",
    )
    manifest = tmp_path / "required-local-gates.json"
    manifest.write_text(
        json.dumps(
            {
                "aggregate_task": "verify:required",
                "workflows": {
                    "workflow.yml": {
                        "aggregate_job": "required",
                        "jobs": {
                            "scan": {"mode": "local", "task": "scan"},
                            "hosted": {
                                "mode": "hosted-only",
                                "reason": "Requires provider-only metadata.",
                            },
                        },
                    }
                },
                "hosted_required_contexts": {"codeql-required": "GitHub-hosted CodeQL analysis."},
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return workflow, taskfile, manifest


def test_repository_required_local_gate_manifest_is_current() -> None:
    module = _load_module()

    assert module.validate_repository(REPO_ROOT) == []


def test_new_required_job_without_manifest_entry_fails(tmp_path: Path) -> None:
    module = _load_module()
    workflow, taskfile, manifest = _fixture(tmp_path)
    workflow.write_text(
        workflow.read_text(encoding="utf-8").replace(
            "needs: [scan, hosted]", "needs: [scan, hosted, new-scan]"
        ),
        encoding="utf-8",
    )

    failures = module.validate_paths(
        root=tmp_path,
        taskfile=taskfile,
        manifest_path=manifest,
    )

    assert any("new-scan" in failure and "manifest" in failure for failure in failures)


def test_local_task_must_be_reachable_from_aggregate(tmp_path: Path) -> None:
    module = _load_module()
    _, taskfile, manifest = _fixture(tmp_path)
    taskfile.write_text(
        taskfile.read_text(encoding="utf-8").replace("      - task: scan\n", ""),
        encoding="utf-8",
    )

    failures = module.validate_paths(
        root=tmp_path,
        taskfile=taskfile,
        manifest_path=manifest,
    )

    assert any("scan" in failure and "verify:required" in failure for failure in failures)


def test_hosted_only_boundary_requires_reason(tmp_path: Path) -> None:
    module = _load_module()
    _, taskfile, manifest = _fixture(tmp_path)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["workflows"]["workflow.yml"]["jobs"]["hosted"]["reason"] = ""
    manifest.write_text(json.dumps(data), encoding="utf-8")

    failures = module.validate_paths(
        root=tmp_path,
        taskfile=taskfile,
        manifest_path=manifest,
    )

    assert any("hosted" in failure and "reason" in failure for failure in failures)
