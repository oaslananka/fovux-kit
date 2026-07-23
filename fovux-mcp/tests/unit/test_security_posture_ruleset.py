"""Tests for canonical GitHub ruleset drift detection."""

from __future__ import annotations

import copy
import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "generate_security_posture.py"
EXPECTED_CHECKS = {
    "ci-required",
    "security-required",
    "dependency-review",
    "codeql-required",
    "elevated-review-required",
}


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_security_posture", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _status_rule(policy: dict[str, object]) -> dict[str, object]:
    rules = policy["rules"]
    assert isinstance(rules, list)
    return next(rule for rule in rules if rule["type"] == "required_status_checks")


def test_tracked_main_ruleset_is_the_solo_maintainer_contract() -> None:
    module = _load_module()
    policy = module._load_main_ruleset_policy()

    assert policy["name"] == "main-ci-solo-maintainer"
    assert policy["conditions"] == {"ref_name": {"include": ["refs/heads/main"], "exclude": []}}
    assert policy["bypass_actors"] == []

    rules = policy["rules"]
    assert isinstance(rules, list)
    rule_types = {rule["type"] for rule in rules}
    assert "required_signatures" not in rule_types

    status_rule = _status_rule(policy)
    parameters = status_rule["parameters"]
    assert isinstance(parameters, dict)
    assert parameters["strict_required_status_checks_policy"] is True
    assert {check["context"] for check in parameters["required_status_checks"]} == EXPECTED_CHECKS


def test_ruleset_comparison_ignores_api_metadata_and_order() -> None:
    module = _load_module()
    expected = module._load_main_ruleset_policy()
    live = copy.deepcopy(expected)
    live["bypass_actors"] = None
    live.update(
        {
            "id": 18689082,
            "node_id": "RRS_example",
            "source": "oaslananka/fovux-kit",
            "source_type": "Repository",
            "created_at": "2026-06-03T00:00:00Z",
            "updated_at": "2026-07-20T00:00:00Z",
        }
    )
    live["rules"] = list(reversed(live["rules"]))
    status_rule = _status_rule(live)
    parameters = status_rule["parameters"]
    parameters["required_status_checks"] = list(reversed(parameters["required_status_checks"]))

    assert module._main_ruleset_deviations(expected, live) == []


def test_ruleset_comparison_detects_missing_check_and_bypass_actor() -> None:
    module = _load_module()
    expected = module._load_main_ruleset_policy()
    live = copy.deepcopy(expected)
    live["bypass_actors"] = [
        {"actor_id": 1, "actor_type": "RepositoryRole", "bypass_mode": "always"}
    ]
    status_rule = _status_rule(live)
    parameters = status_rule["parameters"]
    parameters["required_status_checks"] = [
        check
        for check in parameters["required_status_checks"]
        if check["context"] != "security-required"
    ]

    deviations = module._main_ruleset_deviations(expected, live)

    assert any("bypass" in deviation.lower() for deviation in deviations)
    assert any("security-required" in deviation for deviation in deviations)


def test_restricted_dependabot_access_does_not_skip_public_policy_checks(
    monkeypatch,
) -> None:
    module = _load_module()

    def _restricted(_endpoint: str):
        raise subprocess.CalledProcessError(
            1,
            ["gh", "api"],
            stderr="gh: Resource not accessible by integration (HTTP 403)",
        )

    monkeypatch.setattr(module, "_run_gh_api", _restricted)

    assert module._fetch_dependabot_alerts() is None


def test_admin_security_settings_can_be_unavailable_to_pr_tokens() -> None:
    module = _load_module()

    public_repo_data = {"visibility": "public"}
    admin_repo_data = {
        "security_and_analysis": {
            "secret_scanning": {"status": "enabled"},
        }
    }

    assert module._security_analysis_status(public_repo_data, "secret_scanning") is None
    assert module._display_security_status(None) == "Unavailable"
    assert module._security_analysis_status(admin_repo_data, "secret_scanning") == "enabled"
    assert module._display_security_status("enabled") == "Enabled"
