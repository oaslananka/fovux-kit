"""Contract tests for elevated pull-request review evidence policy."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_review_evidence.py"
POLICY_PATH = REPO_ROOT / ".github" / "review-evidence-policy.json"


def _load_module() -> ModuleType:
    assert SCRIPT_PATH.is_file(), "elevated review checker is missing"
    spec = importlib.util.spec_from_file_location("check_review_evidence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_policy_labels_elevate_pull_requests() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)

    for label in ("risk:high", "size/XL", "requires-review"):
        result = module.classify_elevated(labels={label}, files={"README.md"}, policy=policy)

        assert result.elevated is True
        assert result.label_reasons == (label,)
        assert result.path_reasons == ()


def test_sensitive_paths_elevate_without_labels() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)
    paths = {
        "fovux-mcp/src/fovux/core/auth.py",
        "fovux-mcp/src/fovux/core/processes.py",
        ".github/workflows/security.yml",
        "scripts/publish.sh",
        "fovux-mcp/src/fovux/schemas/training.py",
        "fovux-mcp/migrations/0001_registry.py",
    }

    result = module.classify_elevated(labels=set(), files=paths, policy=policy)

    assert result.elevated is True
    assert result.label_reasons == ()
    assert set(result.path_reasons) == {
        "authentication-authorization:fovux-mcp/src/fovux/core/auth.py",
        "subprocess-execution:fovux-mcp/src/fovux/core/processes.py",
        "workflow-permissions:.github/workflows/security.yml",
        "release-publishing:scripts/publish.sh",
        "registry-schema-migration:fovux-mcp/migrations/0001_registry.py",
        "registry-schema-migration:fovux-mcp/src/fovux/schemas/training.py",
    }


def test_routine_docs_change_is_not_elevated() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)

    result = module.classify_elevated(
        labels={"documentation", "area:docs"},
        files={"docs/testing.md", "README.md"},
        policy=policy,
    )

    assert result.elevated is False
    assert result.label_reasons == ()
    assert result.path_reasons == ()


def test_policy_loader_fails_closed_on_missing_required_keys(tmp_path: Path) -> None:
    module = _load_module()
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "status_context": "elevated-review-required",
                "evidence_marker": "<!-- elevated-review-evidence -->",
                "required_checks": ["ci-required"],
                "authorized_associations": ["OWNER"],
                "sensitive_paths": [{"category": "workflow", "patterns": [".github/workflows/**"]}],
            }
        )
    )

    with pytest.raises(ValueError, match="elevated_labels"):
        module.load_policy(policy_path)


def test_policy_loader_rejects_unsafe_patterns(tmp_path: Path) -> None:
    module = _load_module()
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "status_context": "elevated-review-required",
                "elevated_labels": ["risk:high"],
                "sensitive_paths": [{"category": "workflow", "patterns": ["../outside/**"]}],
                "required_checks": ["ci-required"],
                "authorized_associations": ["OWNER"],
                "ruleset_activation": "bootstrap",
                "evidence_marker": "<!-- elevated-review-evidence -->",
            }
        )
    )

    with pytest.raises(ValueError, match="repository-relative"):
        module.load_policy(policy_path)


HEAD_SHA = "a" * 40
REQUIRED_CHECKS = (
    "ci-required",
    "security-required",
    "dependency-review",
    "codeql-required",
    "Review Threads",
)


def _successful_checks(module: ModuleType) -> tuple[object, ...]:
    return tuple(module.CheckContext(context, "success") for context in REQUIRED_CHECKS)


def _evidence_body(
    *,
    head_sha: str = HEAD_SHA,
    reviewer: str = "oaslananka",
    validation: str | None = None,
    bot_findings: str | None = None,
) -> str:
    validation_text = validation or (
        "ci-required, security-required, dependency-review, codeql-required, "
        "and Review Threads all passed on the current head."
    )
    findings_text = bot_findings or (
        "No findings remain; SonarQube, Codecov, CodeQL, Semgrep, Socket, "
        "and DeepScan were reviewed."
    )
    return "\n".join(
        [
            "<!-- elevated-review-evidence -->",
            f"Head SHA: {head_sha}",
            f"Reviewer: @{reviewer}",
            "Risk assessment: Workflow and governance changes can alter protected merge behavior.",
            f"Validation evidence: {validation_text}",
            f"Bot/agent findings: {findings_text}",
            "Residual risk: Low; revert the policy and workflow commit if the gate "
            "misclassifies PRs.",
        ]
    )


def _snapshot(
    module: ModuleType,
    *,
    author_login: str = "oaslananka",
    author_association: str = "OWNER",
    labels: tuple[str, ...] = ("size/XL",),
    files: tuple[str, ...] = ("README.md",),
    body: str = "",
    html_url: str = "https://github.com/oaslananka/fovux-kit/pull/174",
    reviews: tuple[object, ...] = (),
    checks: tuple[object, ...] | None = None,
    unresolved_threads: int = 0,
) -> object:
    return module.PullRequestSnapshot(
        number=174,
        head_sha=HEAD_SHA,
        author_login=author_login,
        author_association=author_association,
        labels=labels,
        files=files,
        body=body,
        html_url=html_url,
        reviews=reviews,
        checks=_successful_checks(module) if checks is None else checks,
        unresolved_threads=unresolved_threads,
    )


def test_routine_pull_request_succeeds_without_evidence() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)
    snapshot = _snapshot(
        module,
        labels=("documentation",),
        files=("docs/testing.md",),
        checks=(),
    )

    decision = module.evaluate_review_evidence(snapshot, policy)

    assert decision.state == "success"
    assert "Routine" in decision.description


def test_elevated_maintainer_pull_request_requires_public_evidence() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)

    decision = module.evaluate_review_evidence(_snapshot(module), policy)

    assert decision.state == "pending"
    assert "pull request body" in decision.description.lower()


def test_valid_solo_maintainer_evidence_succeeds() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)

    decision = module.evaluate_review_evidence(
        _snapshot(module, body=_evidence_body()),
        policy,
    )

    assert decision.state == "success"
    assert "solo-maintainer" in decision.description.lower()


def test_stale_sha_or_missing_fields_reject_evidence() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)
    stale = _evidence_body(head_sha="b" * 40)
    missing = "\n".join(_evidence_body().splitlines()[:-1])

    for body in (stale, missing):
        decision = module.evaluate_review_evidence(
            _snapshot(module, body=body),
            policy,
        )
        assert decision.state == "pending"
        assert "pull request body" in decision.description.lower()


def test_required_check_failure_fails_and_pending_check_waits() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)

    failed = tuple(
        module.CheckContext(context, "failure" if context == "security-required" else "success")
        for context in REQUIRED_CHECKS
    )
    pending = tuple(
        module.CheckContext(context, "pending" if context == "ci-required" else "success")
        for context in REQUIRED_CHECKS
    )

    failed_decision = module.evaluate_review_evidence(
        _snapshot(module, body=_evidence_body(), checks=failed),
        policy,
    )
    pending_decision = module.evaluate_review_evidence(
        _snapshot(module, body=_evidence_body(), checks=pending),
        policy,
    )

    assert failed_decision.state == "failure"
    assert "security-required" in failed_decision.description
    assert pending_decision.state == "pending"
    assert "ci-required" in pending_decision.description


def test_unresolved_review_threads_block_elevated_evidence() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)

    decision = module.evaluate_review_evidence(
        _snapshot(module, body=_evidence_body(), unresolved_threads=2),
        policy,
    )

    assert decision.state == "pending"
    assert "2 unresolved" in decision.description


def test_external_contributor_requires_current_authorized_approval() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)
    approval = module.Review(
        author_login="maintainer",
        author_association="COLLABORATOR",
        state="APPROVED",
        commit_id=HEAD_SHA,
        html_url="https://example.invalid/review",
    )
    evidence = _evidence_body(reviewer="maintainer")

    waiting = module.evaluate_review_evidence(
        _snapshot(
            module,
            author_login="contributor",
            author_association="CONTRIBUTOR",
            body=evidence,
        ),
        policy,
    )
    approved = module.evaluate_review_evidence(
        _snapshot(
            module,
            author_login="contributor",
            author_association="CONTRIBUTOR",
            body=evidence,
            reviews=(approval,),
        ),
        policy,
    )

    assert waiting.state == "pending"
    assert "approval" in waiting.description.lower()
    assert approved.state == "success"
    assert "external-contributor" in approved.description.lower()


def test_solo_maintainer_evidence_reviewer_must_match_author() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)

    decision = module.evaluate_review_evidence(
        _snapshot(module, body=_evidence_body(reviewer="other-maintainer")),
        policy,
    )

    assert decision.state == "pending"
    assert "reviewer" in decision.description.lower()


def test_stale_self_or_unauthorized_approvals_do_not_count() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)
    invalid_reviews = (
        module.Review("maintainer", "OWNER", "APPROVED", "b" * 40, "https://invalid/stale"),
        module.Review("contributor", "CONTRIBUTOR", "APPROVED", HEAD_SHA, "https://invalid/self"),
        module.Review("outsider", "NONE", "APPROVED", HEAD_SHA, "https://invalid/outsider"),
    )

    decision = module.evaluate_review_evidence(
        _snapshot(
            module,
            author_login="contributor",
            author_association="CONTRIBUTOR",
            body=_evidence_body(reviewer="maintainer"),
            reviews=invalid_reviews,
        ),
        policy,
    )

    assert decision.state == "pending"
    assert "approval" in decision.description.lower()


def test_evidence_must_name_required_checks_and_summarize_bot_findings() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)

    missing_check = module.parse_evidence_body(
        _evidence_body(validation="ci-required and security-required passed."),
        head_sha=HEAD_SHA,
        policy=policy,
    )
    placeholder_findings = module.parse_evidence_body(
        _evidence_body(bot_findings="None"),
        head_sha=HEAD_SHA,
        policy=policy,
    )

    assert missing_check is None
    assert placeholder_findings is None


WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "review-evidence-gate.yml"
RULESET_PATH = REPO_ROOT / ".github" / "rulesets" / "main.json"


def test_base_branch_metadata_workflow_is_safe_and_audited() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "pull_request_target:" in workflow
    assert "zizmor: ignore[dangerous-triggers]" in workflow
    assert "base-only metadata gate" in workflow
    assert "ref: ${{ github.event.pull_request.base.sha }}" in workflow
    assert "persist-credentials: false" in workflow
    assert "python scripts/check_review_evidence.py" in workflow
    for permission in (
        "contents: read",
        "pull-requests: read",
        "checks: read",
        "statuses: write",
    ):
        assert permission in workflow
    for forbidden in (
        "workflow_run:",
        "issue_comment:",
        "pull_request_review_comment:",
        "pull_request.head.ref",
        "github.head_ref",
        "refs/pull",
        "gh pr checkout",
    ):
        assert forbidden not in workflow


def test_event_resolution_only_accepts_pull_request_events() -> None:
    module = _load_module()

    assert module.resolve_pull_request_number({"pull_request": {"number": 174}}) == 174
    assert (
        module.resolve_pull_request_number(
            {"issue": {"number": 174, "pull_request": {"url": "https://example.invalid/pr"}}}
        )
        is None
    )
    assert (
        module.resolve_pull_request_number({"workflow_run": {"pull_requests": [{"number": 174}]}})
        is None
    )


def test_run_for_pull_request_writes_policy_status() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)
    snapshot = _snapshot(
        module,
        labels=("documentation",),
        files=("docs/testing.md",),
        checks=(),
    )

    class FakeClient:
        def __init__(self) -> None:
            self.statuses: list[tuple[str, str, str, object, str]] = []

        def fetch_snapshot(
            self,
            repository: str,
            number: int,
            required_checks: tuple[str, ...],
        ) -> object:
            assert repository == "oaslananka/fovux-kit"
            assert number == 174
            assert required_checks == REQUIRED_CHECKS
            return snapshot

        def create_status(
            self,
            repository: str,
            sha: str,
            context: str,
            decision: object,
            target_url: str,
        ) -> None:
            self.statuses.append((repository, sha, context, decision, target_url))

    client = FakeClient()
    decision = module.run_for_pull_request(
        client=client,
        repository="oaslananka/fovux-kit",
        number=174,
        policy=policy,
    )

    assert decision.state == "success"
    assert client.statuses == [
        (
            "oaslananka/fovux-kit",
            HEAD_SHA,
            "elevated-review-required",
            decision,
            "https://github.com/oaslananka/fovux-kit/pull/174",
        )
    ]


CONTRACT_PATHS = (
    ".github/review-evidence-policy.json",
    ".github/workflows/review-evidence-gate.yml",
    ".github/workflows/review-thread-gate.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/rulesets/main.json",
    "docs/elevated-review-policy.md",
    "docs/branch-protection.md",
    "Taskfile.yml",
)


def _copy_contract_tree(tmp_path: Path) -> Path:
    import shutil

    for relative in CONTRACT_PATHS:
        source = REPO_ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.exists():
            shutil.copy2(source, destination)
    return tmp_path


def test_repository_policy_is_active_after_ruleset_activation() -> None:
    module = _load_module()
    policy = module.load_policy(POLICY_PATH)

    assert policy["ruleset_activation"] == "active"


def test_repository_review_evidence_contract_is_synchronized() -> None:
    module = _load_module()

    assert module.validate_repository(REPO_ROOT) == []


def test_repository_validation_detects_missing_template_evidence(tmp_path: Path) -> None:
    module = _load_module()
    root = _copy_contract_tree(tmp_path)
    template = root / ".github" / "PULL_REQUEST_TEMPLATE.md"
    template.write_text("## Summary\n")

    failures = module.validate_repository(root)

    assert any("template" in failure.lower() for failure in failures)
    assert any("elevated-review-evidence" in failure for failure in failures)


def test_repository_validation_rejects_dangerous_trigger_or_untrusted_checkout(
    tmp_path: Path,
) -> None:
    module = _load_module()
    root = _copy_contract_tree(tmp_path)
    workflow = root / ".github" / "workflows" / "review-evidence-gate.yml"
    workflow.write_text(
        workflow.read_text(encoding="utf-8")
        + "\n# unsafe github.head_ref refs/pull gh pr checkout\n"
    )

    failures = module.validate_repository(root)

    assert any("untrusted" in failure.lower() for failure in failures)


def test_active_policy_requires_ruleset_context(tmp_path: Path) -> None:
    module = _load_module()
    root = _copy_contract_tree(tmp_path)
    ruleset_path = root / ".github" / "rulesets" / "main.json"
    ruleset = json.loads(ruleset_path.read_text(encoding="utf-8"))
    status_rule = next(
        rule for rule in ruleset["rules"] if rule["type"] == "required_status_checks"
    )
    status_rule["parameters"]["required_status_checks"] = [
        check
        for check in status_rule["parameters"]["required_status_checks"]
        if check["context"] != "elevated-review-required"
    ]
    ruleset_path.write_text(json.dumps(ruleset))

    failures = module.validate_repository(root)

    assert any("ruleset" in failure.lower() for failure in failures)
    assert any("elevated-review-required" in failure for failure in failures)


def test_bootstrap_policy_rejects_premature_ruleset_context(tmp_path: Path) -> None:
    module = _load_module()
    root = _copy_contract_tree(tmp_path)
    policy_path = root / ".github" / "review-evidence-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["ruleset_activation"] = "bootstrap"
    policy_path.write_text(json.dumps(policy))

    failures = module.validate_repository(root)

    assert any("bootstrap" in failure.lower() for failure in failures)


def test_review_thread_gate_emits_status_for_direct_ready_pr_opening() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "review-thread-gate.yml").read_text(
        encoding="utf-8"
    )

    assert "types: [opened, synchronize, reopened, ready_for_review]" in workflow
