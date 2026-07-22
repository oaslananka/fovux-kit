"""Tests for truthful registry verification retry evidence."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_registry_releases.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_registry_releases", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_evidence_summary_counts_passed_and_skipped_checks(tmp_path: Path) -> None:
    module = _load_module()
    path = tmp_path / "evidence.json"
    evidence = module.EvidenceRecorder(path=path, expected_versions={"studio": "1.2.3"})
    evidence.record(channel="studio", check="registry", status="passed")
    evidence.record(
        channel="studio",
        check="smoke",
        status="skipped",
        details={"reason": "disabled for this run"},
    )

    evidence.write()

    payload = _payload(path)
    assert payload["schema_version"] == 2
    assert payload["summary"] == {
        "passed": 1,
        "failed": 0,
        "skipped": 1,
        "retries": 0,
    }


def test_success_after_retries_has_no_terminal_failures(tmp_path: Path) -> None:
    module = _load_module()
    path = tmp_path / "evidence.json"
    evidence = module.EvidenceRecorder(path=path, expected_versions={})
    attempts = 0

    def flaky(recorder: object) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            recorder.record(
                channel="studio",
                check="marketplace",
                status="failed",
                details={"error": "not visible yet"},
            )
            raise RuntimeError("not visible yet")
        recorder.record(channel="studio", check="marketplace", status="passed")

    module.run_with_retry(flaky, evidence=evidence, retries=3, delay=0)
    evidence.write()

    payload = _payload(path)
    assert [step["status"] for step in payload["steps"]] == [
        "retry",
        "retry",
        "passed",
    ]
    assert payload["summary"] == {
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "retries": 2,
    }


def test_exhausted_retry_keeps_only_terminal_failure(tmp_path: Path) -> None:
    module = _load_module()
    path = tmp_path / "evidence.json"
    evidence = module.EvidenceRecorder(path=path, expected_versions={})

    def unavailable(recorder: object) -> None:
        recorder.record(
            channel="studio",
            check="marketplace",
            status="failed",
            details={"error": "still unavailable"},
        )
        raise RuntimeError("still unavailable")

    with pytest.raises(RuntimeError, match="still unavailable"):
        module.run_with_retry(unavailable, evidence=evidence, retries=2, delay=0)
    evidence.write()

    payload = _payload(path)
    assert [step["status"] for step in payload["steps"]] == ["retry", "failed"]
    assert payload["summary"] == {
        "passed": 0,
        "failed": 1,
        "skipped": 0,
        "retries": 1,
    }
