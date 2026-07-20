"""Generate fovux-kit security posture report and check for policy drift.

Fetches configuration from GitHub API via gh CLI and checks local files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_FILE = REPO_ROOT / "docs" / "security-posture.md"
MAIN_RULESET_FILE = REPO_ROOT / ".github" / "rulesets" / "main.json"


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


def _load_main_ruleset_policy(path: Path | None = None) -> dict[str, Any]:
    """Load the canonical tracked main-branch ruleset policy."""
    policy_path = path or MAIN_RULESET_FILE
    data = json.loads(policy_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {policy_path}")
    return data


def _canonicalize(value: object) -> object:
    """Normalize JSON-like values where list ordering is not policy-semantic."""
    if isinstance(value, dict):
        return {key: _canonicalize(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        normalized = [_canonicalize(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    return value


def _normalize_main_ruleset_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Strip API metadata and normalize the semantic ruleset request fields."""
    semantic_keys = (
        "name",
        "target",
        "enforcement",
        "conditions",
        "rules",
        "bypass_actors",
    )
    return {key: _canonicalize(policy.get(key)) for key in semantic_keys}


def _required_status_checks(policy: dict[str, Any]) -> set[str]:
    """Return required status-check contexts from a ruleset payload."""
    rules = policy.get("rules", [])
    if not isinstance(rules, list):
        return set()
    status_rule = next(
        (rule for rule in rules if rule.get("type") == "required_status_checks"),
        None,
    )
    if not isinstance(status_rule, dict):
        return set()
    parameters = status_rule.get("parameters", {})
    if not isinstance(parameters, dict):
        return set()
    checks = parameters.get("required_status_checks", [])
    if not isinstance(checks, list):
        return set()
    return {
        context
        for check in checks
        if isinstance(check, dict) and isinstance((context := check.get("context")), str)
    }


def _is_restricted_api_error(exc: subprocess.CalledProcessError) -> bool:
    """Return whether GitHub rejected an endpoint for token permission reasons."""
    details = f"{exc.stderr or ''}\n{exc.output or ''}".lower()
    return any(marker in details for marker in ("403", "resource not accessible", "permission"))


def _fetch_dependabot_alerts() -> list[Any] | None:
    """Fetch Dependabot alerts, returning None when the token cannot read them."""
    try:
        data = _run_gh_api("repos/oaslananka/fovux-kit/dependabot/alerts")
    except subprocess.CalledProcessError as exc:
        if _is_restricted_api_error(exc):
            print(
                "Dependabot alerts are unavailable to the current token; "
                "continuing with ruleset and public security posture validation."
            )
            return None
        raise
    if not isinstance(data, list):
        raise ValueError("Expected list from dependabot alerts endpoint")
    return data


def _main_ruleset_deviations(expected: dict[str, Any], live: dict[str, Any]) -> list[str]:
    """Describe semantic drift between tracked and live main rulesets."""
    deviations: list[str] = []
    name = str(expected.get("name", "main ruleset"))

    bypass_actors = live.get("bypass_actors", [])
    if bypass_actors:
        deviations.append(f"{name} has bypass actors: {bypass_actors}")

    expected_checks = _required_status_checks(expected)
    live_checks = _required_status_checks(live)
    missing_checks = sorted(expected_checks - live_checks)
    extra_checks = sorted(live_checks - expected_checks)
    if missing_checks:
        deviations.append(f"{name} missing status checks: {missing_checks}")
    if extra_checks:
        deviations.append(f"{name} has untracked status checks: {extra_checks}")

    if _normalize_main_ruleset_policy(expected) != _normalize_main_ruleset_policy(live):
        deviations.append(f"{name} live policy differs from .github/rulesets/main.json")

    return deviations


def main() -> int:
    """Run security posture generation and validation."""
    parser = argparse.ArgumentParser(description="Generate security posture report.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any policy drift or API error is detected.",
    )
    args = parser.parse_args()

    try:
        expected_main_ruleset = _load_main_ruleset_policy()
    except (OSError, ValueError) as exc:
        print(f"Invalid tracked main ruleset policy: {exc}")
        return 1 if args.strict else 0

    # 1. Fetch GitHub API data
    try:
        repo_data = _run_gh_api("repos/oaslananka/fovux-kit")
        if not isinstance(repo_data, dict):
            raise ValueError("Expected dictionary from repo endpoint")

        rulesets_data = _run_gh_api("repos/oaslananka/fovux-kit/rulesets")
        if not isinstance(rulesets_data, list):
            raise ValueError("Expected list from rulesets endpoint")

        detailed_rulesets: list[dict[str, Any]] = []
        for ruleset_summary in rulesets_data:
            if not isinstance(ruleset_summary, dict):
                raise ValueError("Expected ruleset summary objects")
            ruleset_id = ruleset_summary.get("id")
            if ruleset_id:
                ruleset_detail = _run_gh_api(f"repos/oaslananka/fovux-kit/rulesets/{ruleset_id}")
                if not isinstance(ruleset_detail, dict):
                    raise ValueError("Expected ruleset detail object")
                detailed_rulesets.append(ruleset_detail)

        envs_data = _run_gh_api("repos/oaslananka/fovux-kit/environments")
        if not isinstance(envs_data, dict):
            raise ValueError("Expected dictionary from environments endpoint")

    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as exc:
        err_msg = str(exc)
        if isinstance(exc, subprocess.CalledProcessError):
            err_msg += f"\nStderr: {exc.stderr or exc.output or ''}"
        print(f"Error communicating with GitHub API: {err_msg}")
        if args.strict:
            return 1
        print("Skipping dynamic checks (offline or unauthorized).")
        return 0

    try:
        alerts_data = _fetch_dependabot_alerts()
    except (subprocess.CalledProcessError, ValueError) as exc:
        print(f"Error reading Dependabot alerts: {exc}")
        if args.strict:
            return 1
        alerts_data = None

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

    # Analyze rulesets against the tracked canonical policy.
    main_ruleset_name = str(expected_main_ruleset.get("name", ""))
    main_ruleset = next(
        (ruleset for ruleset in detailed_rulesets if ruleset.get("name") == main_ruleset_name),
        None,
    )
    tag_ruleset = next(
        (
            ruleset
            for ruleset in detailed_rulesets
            if ruleset.get("name") == "release-tag-protection"
        ),
        None,
    )

    if not main_ruleset:
        deviations.append(f"Ruleset '{main_ruleset_name}' is missing")
    elif isinstance(main_ruleset, dict):
        deviations.extend(_main_ruleset_deviations(expected_main_ruleset, main_ruleset))

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

    # Dependabot Alerts check. Ruleset validation remains strict when this
    # privileged endpoint is unavailable to the workflow token.
    open_alerts = (
        [alert for alert in alerts_data if alert.get("state") == "open"]
        if alerts_data is not None
        else []
    )
    critical_or_high_alerts = [
        alert
        for alert in open_alerts
        if alert.get("security_advisory", {}).get("severity") in ("critical", "high")
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
                f"- **{main_ruleset_name}:** Enforcement `{main_ruleset.get('enforcement')}`",
                f"  - Deletion prevented: {has_deletion}",
                f"  - Linear history required: {has_linear}",
                f"  - Commit signatures required: {has_sigs}",
                "  - Required status checks:",
            ]
        )
        for check in status_checks:
            report_lines.append(f"    - `{check}`")
    else:
        report_lines.append(f"- **{main_ruleset_name}:** Missing")

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
            (
                f"- **Total Open Alerts:** {len(open_alerts)}"
                if alerts_data is not None
                else "- **Total Open Alerts:** Unavailable to current token"
            ),
        ]
    )
    if alerts_data is not None:
        severities = ["critical", "high", "medium", "low"]
        for severity in severities:
            count = len(
                [
                    alert
                    for alert in open_alerts
                    if alert.get("security_advisory", {}).get("severity") == severity
                ]
            )
            report_lines.append(f"  - **{severity.capitalize()}:** {count}")

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
