"""Generate fovux-kit security posture report and check for policy drift.

Fetches configuration from GitHub API via gh CLI and checks local files.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_FILE = REPO_ROOT / "docs" / "security-posture.md"


def _run_gh_api(endpoint: str) -> dict[str, Any] | list[Any]:
    """Execute gh api and parse JSON response."""
    cmd = ["gh", "api", endpoint]
    result = subprocess.run(  # noqa: S603
        cmd, capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)  # type: ignore[no-any-return]


def check_local_governance() -> dict[str, bool]:
    """Verify presence of required security workflows and build scripts."""
    checks = {
        "security_workflow": (REPO_ROOT / ".github/workflows/security.yml").exists(),
        "codeql_workflow": (REPO_ROOT / ".github/workflows/codeql.yml").exists(),
        "scorecard_workflow": (REPO_ROOT / ".github/workflows/scorecard.yml").exists(),
        "python_sbom_script": (REPO_ROOT / "scripts/build_spdx_sbom.py").exists(),
        "node_sbom_script": (REPO_ROOT / "scripts/build_node_spdx_sbom.mjs").exists(),
    }
    return checks


def main() -> int:
    """Run security posture generation and validation."""
    parser = argparse.ArgumentParser(description="Generate security posture report.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any policy drift or API error is detected.",
    )
    args = parser.parse_args()

    # 1. Fetch GitHub API data
    try:
        repo_data = _run_gh_api("repos/oaslananka/fovux-kit")
        if not isinstance(repo_data, dict):
            raise ValueError("Expected dictionary from repo endpoint")

        rulesets_data = _run_gh_api("repos/oaslananka/fovux-kit/rulesets")
        if not isinstance(rulesets_data, list):
            raise ValueError("Expected list from rulesets endpoint")

        detailed_rulesets = []
        for rs in rulesets_data:
            rs_id = rs.get("id")
            if rs_id:
                rs_detail = _run_gh_api(f"repos/oaslananka/fovux-kit/rulesets/{rs_id}")
                detailed_rulesets.append(rs_detail)

        alerts_data = _run_gh_api("repos/oaslananka/fovux-kit/dependabot/alerts")
        if not isinstance(alerts_data, list):
            raise ValueError("Expected list from dependabot alerts endpoint")

        envs_data = _run_gh_api("repos/oaslananka/fovux-kit/environments")
        if not isinstance(envs_data, dict):
            raise ValueError("Expected dictionary from environments endpoint")

    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as exc:
        err_msg = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            err_msg += f"\nStderr: {exc.stderr or exc.output or ''}"
        print(f"Error communicating with GitHub API: {err_msg}")
        is_restricted = any(
            x in err_msg.lower() for x in ("403", "404", "resource not accessible", "permission")
        )
        if args.strict and os.environ.get("GITHUB_ACTIONS") == "true" and is_restricted:
            print(
                "Restricted GITHUB_TOKEN permissions detected (e.g. fork PR). "
                "Skipping strict posture checks."
            )
            return 0
        if args.strict:
            return 1
        print("Skipping dynamic checks (offline or unauthorized).")
        return 0

    # 2. Check local governance
    local_checks = check_local_governance()

    # 3. Analyze policies & build report
    deviations: list[str] = []

    # Visibility & Security properties
    visibility = repo_data.get("visibility", "unknown")
    if visibility != "public":
        deviations.append(f"Repo visibility is {visibility} (expected public)")

    security_analysis = repo_data.get("security_and_analysis", {})
    secret_scanning = security_analysis.get("secret_scanning", {}).get("status")
    push_protection = security_analysis.get("secret_scanning_push_protection", {}).get("status")
    dependabot_updates = security_analysis.get("dependabot_security_updates", {}).get("status")

    if secret_scanning != "enabled":  # noqa: S105
        deviations.append("Secret scanning is not enabled")
    if push_protection != "enabled":
        deviations.append("Secret scanning push protection is not enabled")
    if dependabot_updates != "enabled":
        deviations.append("Dependabot security updates are not enabled")

    # Analyze rulesets
    main_ruleset = next((r for r in detailed_rulesets if r.get("name") == "main-protection"), None)
    tag_ruleset = next(
        (r for r in detailed_rulesets if r.get("name") == "release-tag-protection"), None
    )

    if not main_ruleset:
        deviations.append("Ruleset 'main-protection' is missing")
    else:
        rules = main_ruleset.get("rules", [])
        rule_types = {r.get("type") for r in rules}

        if main_ruleset.get("enforcement") != "active":
            deviations.append("main-protection is not active")
        if "deletion" not in rule_types:
            deviations.append("main-protection does not prevent deletion")
        if "non_fast_forward" not in rule_types:
            deviations.append("main-protection does not prevent non-fast-forward push")
        if "required_linear_history" not in rule_types:
            deviations.append("main-protection does not require linear history")
        if "required_signatures" not in rule_types:
            deviations.append("main-protection does not require signatures")

        # Status checks check
        status_checks_rule = next(
            (r for r in rules if r.get("type") == "required_status_checks"), None
        )
        if not status_checks_rule:
            deviations.append("main-protection does not require status checks")
        else:
            params = status_checks_rule.get("parameters", {})
            req_checks = params.get("required_status_checks", [])
            checks = {c.get("context") for c in req_checks}
            expected_checks = {
                "ci-required",
                "security-required",
                "codeql-required",
                "scorecard-required",
                "release-please",
            }
            missing_checks = expected_checks - checks
            if missing_checks:
                deviations.append(
                    f"main-protection missing status checks: {sorted(missing_checks)}"
                )

        # Pull request thread resolution check
        pr_rule = next((r for r in rules if r.get("type") == "pull_request"), None)
        if not pr_rule:
            deviations.append("main-protection does not require pull requests")
        else:
            params = pr_rule.get("parameters", {})
            if not params.get("required_review_thread_resolution"):
                deviations.append("main-protection does not require review thread resolution")

    if not tag_ruleset:
        deviations.append("Ruleset 'release-tag-protection' is missing")
    else:
        rules = tag_ruleset.get("rules", [])
        rule_types = {r.get("type") for r in rules}
        if tag_ruleset.get("enforcement") != "active":
            deviations.append("release-tag-protection is not active")
        if "deletion" not in rule_types:
            deviations.append("release-tag-protection does not prevent tag deletion")
        if "non_fast_forward" not in rule_types:
            deviations.append("release-tag-protection does not prevent non-fast-forward tags")

    # Dependabot Alerts check
    open_alerts = [a for a in alerts_data if a.get("state") == "open"]
    critical_or_high_alerts = [
        a
        for a in open_alerts
        if a.get("security_advisory", {}).get("severity") in ("critical", "high")
    ]
    if critical_or_high_alerts:
        deviations.append(
            f"Found {len(critical_or_high_alerts)} open Critical or High Dependabot alerts"
        )

    # Generate Markdown Report
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S") + " UTC"

    sec_scan_status = secret_scanning.capitalize() if secret_scanning else "Disabled"
    push_prot_status = push_protection.capitalize() if push_protection else "Disabled"
    dep_up_status = dependabot_updates.capitalize() if dependabot_updates else "Disabled"

    report_lines = [
        "# Fovux Security Posture Report",
        "",
        f"Generated on: {timestamp}",
        "",
        "## Summary",
        f"- **Visibility:** {visibility.capitalize()}",
        f"- **Secret Scanning:** {sec_scan_status}",
        f"- **Secret Scanning Push Protection:** {push_prot_status}",
        f"- **Dependabot Security Updates:** {dep_up_status}",
        "",
        "## Branch & Tag Protection Rulesets",
    ]

    if main_ruleset:
        rules = main_ruleset.get("rules", [])
        rule_types = {r.get("type") for r in rules}
        status_checks_rule = next(
            (r for r in rules if r.get("type") == "required_status_checks"), None
        )
        status_checks = []
        if status_checks_rule:
            params = status_checks_rule.get("parameters", {})
            status_checks = [c.get("context") for c in params.get("required_status_checks", [])]

        has_linear = "Yes" if "required_linear_history" in rule_types else "No"
        has_sigs = "Yes" if "required_signatures" in rule_types else "No"
        has_deletion = "Yes" if "deletion" in rule_types else "No"

        report_lines.extend(
            [
                f"- **main-protection:** Enforcement `{main_ruleset.get('enforcement')}`",
                f"  - Deletion prevented: {has_deletion}",
                f"  - Linear history required: {has_linear}",
                f"  - Commit signatures required: {has_sigs}",
                "  - Required status checks:",
            ]
        )
        for check in status_checks:
            report_lines.append(f"    - `{check}`")
    else:
        report_lines.append("- **main-protection:** Missing")

    if tag_ruleset:
        rules = tag_ruleset.get("rules", [])
        rule_types = {r.get("type") for r in rules}
        tag_deletion = "Yes" if "deletion" in rule_types else "No"
        tag_fff = "Yes" if "non_fast_forward" in rule_types else "No"

        report_lines.extend(
            [
                f"- **release-tag-protection:** Enforcement `{tag_ruleset.get('enforcement')}`",
                f"  - Tag deletion prevented: {tag_deletion}",
                f"  - Tag non-fast-forward prevented: {tag_fff}",
            ]
        )
    else:
        report_lines.append("- **release-tag-protection:** Missing")

    report_lines.extend(
        [
            "",
            "## Dependabot Alerts Summary",
            f"- **Total Open Alerts:** {len(open_alerts)}",
        ]
    )
    severities = ["critical", "high", "medium", "low"]
    for sev in severities:
        count = len(
            [a for a in open_alerts if a.get("security_advisory", {}).get("severity") == sev]
        )
        report_lines.append(f"  - **{sev.capitalize()}:** {count}")

    report_lines.extend(
        [
            "",
            "## Deployment Environments",
        ]
    )
    envs = envs_data.get("environments", [])
    for env in envs:
        env_name = env.get("name")
        rules_count = len(env.get("protection_rules", []))
        report_lines.append(
            f"- **{env_name}:** {'Protected' if rules_count > 0 else 'No protection rules'}"
        )

    report_lines.extend(
        [
            "",
            "## Governance & Security Workflows",
            f"- Security workflow (.github/workflows/security.yml): "
            f"{'Present' if local_checks['security_workflow'] else 'Missing'}",
            f"- CodeQL workflow (.github/workflows/codeql.yml): "
            f"{'Present' if local_checks['codeql_workflow'] else 'Missing'}",
            f"- Scorecard workflow (.github/workflows/scorecard.yml): "
            f"{'Present' if local_checks['scorecard_workflow'] else 'Missing'}",
            f"- Python SPDX SBOM generator: "
            f"{'Present' if local_checks['python_sbom_script'] else 'Missing'}",
            f"- Node.js SPDX SBOM generator: "
            f"{'Present' if local_checks['node_sbom_script'] else 'Missing'}",
            "",
        ]
    )

    DOCS_FILE.parent.mkdir(parents=True, exist_ok=True)
    DOCS_FILE.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Generated security posture report at {DOCS_FILE}")

    # Report results
    if deviations:
        print("\nCRITICAL SECURITY POLICY DEVIATIONS DETECTED:")
        for dev in deviations:
            print(f"  - {dev}")
        if args.strict:
            return 1

    print("\nSecurity posture validation succeeded (no critical deviations).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
