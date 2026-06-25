"""Validate workbench roadmap closure quality gates."""

from __future__ import annotations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REQUIRED = [
    "check_docs_truth.py",
    "check_agent_policy.py",
    "check_http_security_policy.py",
    "check_audit_schema.py",
    "check_train_preflight_gate.py",
    "check_guided_workflow.py",
    "check_dataset_intelligence.py",
]
REQUIRED += [
    "check_review_queue.py",
    "check_dashboard_resilience.py",
    "check_export_matrix.py",
    "check_deployment_profiles.py",
    "check_benchmark_reproducibility.py",
    "check_int8_workflow.py",
    "check_license_boundaries.py",
]
REQUIRED += [
    "check_api_stability_plan.py",
    "check_supply_chain_publishing.py",
    "check_mcp_threat_model.py",
    "check_governance_lifecycle.py",
    "check_studio_e2e_smoke.py",
    "check_studio_release_evidence.py",
    "check_mcp_apps_strategy.py",
]


def main() -> int:
    failures: list[str] = []
    for filename in REQUIRED:
        if not (ROOT / "scripts" / filename).exists():
            failures.append(f"Missing readiness gate: {filename}")
    docs = (ROOT / "docs" / "verifiable-workbench-readiness.md").read_text(
        encoding="utf-8"
    )
    for phrase in [
        "Release/version",
        "Risky actions",
        "Training/export",
        "Dataset",
        "Studio",
        "Governance",
    ]:
        if phrase not in docs:
            failures.append(f"Readiness docs missing {phrase}")
    if failures:
        for failure in failures:
            print(f"ERROR: {failure}")
        return 1
    print("Workbench readiness checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
