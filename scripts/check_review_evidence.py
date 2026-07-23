"""Classify and enforce elevated pull-request review evidence."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Collection, Mapping, Sequence
from pathlib import Path
from typing import NamedTuple, Protocol, cast

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POLICY_PATH = ROOT / ".github" / "review-evidence-policy.json"


class Classification(NamedTuple):
    """Stable reasons explaining whether a pull request is elevated."""

    elevated: bool
    label_reasons: tuple[str, ...]
    path_reasons: tuple[str, ...]


class Review(NamedTuple):
    """Pull-request review metadata."""

    author_login: str
    author_association: str
    state: str
    commit_id: str
    html_url: str


class CheckContext(NamedTuple):
    """Combined required-check state for the pull-request head."""

    context: str
    state: str


class PullRequestSnapshot(NamedTuple):
    """Immutable pull-request metadata required by the policy engine."""

    number: int
    head_sha: str
    author_login: str
    author_association: str
    labels: tuple[str, ...]
    files: tuple[str, ...]
    body: str
    html_url: str
    reviews: tuple[Review, ...]
    checks: tuple[CheckContext, ...]
    unresolved_threads: int


class Evidence(NamedTuple):
    """Validated structured review evidence bound to one head SHA."""

    head_sha: str
    reviewer: str
    risk_assessment: str
    validation_evidence: str
    bot_agent_findings: str
    residual_risk: str
    evidence_url: str


class Decision(NamedTuple):
    """Commit-status decision produced by the policy engine."""

    state: str
    description: str
    reasons: tuple[str, ...]


def _string_list(value: object, *, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"Policy field {field} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"Policy field {field} must contain non-empty strings")
    items = cast(list[str], value)
    if len(items) != len(set(items)):
        raise ValueError(f"Policy field {field} must not contain duplicates")
    return items


def load_policy(path: Path = DEFAULT_POLICY_PATH) -> dict[str, object]:
    """Load and validate the repository-owned elevated-review policy."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Review evidence policy must be a JSON object")
    policy = cast(dict[str, object], raw)

    for field in ("status_context", "evidence_marker"):
        value = policy.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Policy field {field} must be a non-empty string")

    _string_list(policy.get("elevated_labels"), field="elevated_labels")
    _string_list(policy.get("required_checks"), field="required_checks")
    _string_list(policy.get("authorized_associations"), field="authorized_associations")
    activation = policy.get("ruleset_activation")
    if activation not in {"bootstrap", "active"}:
        raise ValueError("Policy field ruleset_activation must be bootstrap or active")

    sensitive_paths = policy.get("sensitive_paths")
    if not isinstance(sensitive_paths, list) or not sensitive_paths:
        raise ValueError("Policy field sensitive_paths must be a non-empty list")

    categories: set[str] = set()
    all_patterns: set[str] = set()
    for index, entry in enumerate(sensitive_paths):
        if not isinstance(entry, dict):
            raise ValueError(f"Sensitive path entry {index} must be an object")
        category = entry.get("category")
        if not isinstance(category, str) or not category.strip():
            raise ValueError(f"Sensitive path entry {index} requires a category")
        if category in categories:
            raise ValueError(f"Sensitive path category is duplicated: {category}")
        categories.add(category)
        patterns = _string_list(entry.get("patterns"), field=f"sensitive_paths[{index}].patterns")
        for pattern in patterns:
            path = Path(pattern)
            if path.is_absolute() or ".." in path.parts or pattern.startswith("/"):
                raise ValueError(f"Sensitive path pattern must be repository-relative: {pattern}")
            if pattern in all_patterns:
                raise ValueError(f"Sensitive path pattern is duplicated: {pattern}")
            all_patterns.add(pattern)

    return policy


def classify_elevated(
    *,
    labels: Collection[str],
    files: Collection[str],
    policy: Mapping[str, object],
) -> Classification:
    """Classify a pull request from immutable paths plus policy labels."""
    elevated_labels = set(_string_list(policy.get("elevated_labels"), field="elevated_labels"))
    label_reasons = tuple(sorted(elevated_labels.intersection(labels)))

    sensitive_paths = policy.get("sensitive_paths")
    if not isinstance(sensitive_paths, list):
        raise ValueError("Policy field sensitive_paths must be a list")

    path_reasons: set[str] = set()
    for entry in sensitive_paths:
        if not isinstance(entry, dict):
            raise ValueError("Sensitive path entries must be objects")
        category = entry.get("category")
        patterns = entry.get("patterns")
        if not isinstance(category, str) or not isinstance(patterns, list):
            raise ValueError("Sensitive path entries require category and patterns")
        for filename in files:
            if any(
                isinstance(pattern, str) and fnmatch.fnmatchcase(filename, pattern)
                for pattern in patterns
            ):
                path_reasons.add(f"{category}:{filename}")

    sorted_paths = tuple(sorted(path_reasons))
    return Classification(
        elevated=bool(label_reasons or sorted_paths),
        label_reasons=label_reasons,
        path_reasons=sorted_paths,
    )


_EVIDENCE_FIELDS = {
    "Head SHA": "head_sha",
    "Reviewer": "reviewer",
    "Risk assessment": "risk_assessment",
    "Validation evidence": "validation_evidence",
    "Bot/agent findings": "bot_agent_findings",
    "Residual risk": "residual_risk",
}
_PLACEHOLDER_VALUES = {"", "none", "n/a", "na", "no", "tbd", "todo", "pending"}
_SUCCESS_STATES = {"success"}
_FAILURE_STATES = {"failure", "error", "cancelled", "timed_out", "action_required"}


def _structured_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in body.splitlines():
        for label, name in _EVIDENCE_FIELDS.items():
            prefix = f"{label}:"
            if line.startswith(prefix):
                fields[name] = line.removeprefix(prefix).strip()
                break
    return fields


def parse_evidence_body(
    body: str,
    *,
    head_sha: str,
    policy: Mapping[str, object],
    evidence_url: str = "",
) -> Evidence | None:
    """Parse structured review evidence from the current pull-request body."""
    marker = policy.get("evidence_marker")
    if not isinstance(marker, str) or marker not in body:
        return None

    fields = _structured_fields(body)
    if set(fields) != set(_EVIDENCE_FIELDS.values()):
        return None
    evidence_sha = fields["head_sha"].lower()
    if not re.fullmatch(r"[0-9a-f]{40}", evidence_sha) or evidence_sha != head_sha.lower():
        return None
    reviewer_match = re.fullmatch(r"@([A-Za-z0-9-]+)", fields["reviewer"])
    if reviewer_match is None:
        return None

    risk_assessment = fields["risk_assessment"]
    validation_evidence = fields["validation_evidence"]
    bot_agent_findings = fields["bot_agent_findings"]
    residual_risk = fields["residual_risk"]
    if len(risk_assessment) < 20 or len(validation_evidence) < 20 or len(residual_risk) < 10:
        return None
    if bot_agent_findings.strip().lower() in _PLACEHOLDER_VALUES or len(bot_agent_findings) < 20:
        return None
    required_checks = _string_list(policy.get("required_checks"), field="required_checks")
    if any(context not in validation_evidence for context in required_checks):
        return None

    return Evidence(
        head_sha=evidence_sha,
        reviewer=reviewer_match.group(1),
        risk_assessment=risk_assessment,
        validation_evidence=validation_evidence,
        bot_agent_findings=bot_agent_findings,
        residual_risk=residual_risk,
        evidence_url=evidence_url,
    )


def _latest_reviews_by_author(reviews: Sequence[Review]) -> dict[str, Review]:
    latest: dict[str, Review] = {}
    for review in reviews:
        latest[review.author_login.lower()] = review
    return latest


def evaluate_review_evidence(
    snapshot: PullRequestSnapshot,
    policy: Mapping[str, object],
) -> Decision:
    """Evaluate elevated-review evidence without performing network I/O."""
    classification = classify_elevated(
        labels=snapshot.labels,
        files=snapshot.files,
        policy=policy,
    )
    if not classification.elevated:
        return Decision(
            "success",
            "Routine change; elevated review evidence is not required",
            (),
        )

    if snapshot.unresolved_threads:
        return Decision(
            "pending",
            f"{snapshot.unresolved_threads} unresolved review thread(s) block elevated review",
            ("unresolved-review-threads",),
        )

    required_checks = _string_list(policy.get("required_checks"), field="required_checks")
    check_states = {check.context: check.state.lower() for check in snapshot.checks}
    for context in required_checks:
        state = check_states.get(context)
        if state in _FAILURE_STATES:
            return Decision(
                "failure",
                f"Required check {context} concluded {state}",
                (f"failed-check:{context}",),
            )
    for context in required_checks:
        state = check_states.get(context)
        if state not in _SUCCESS_STATES:
            rendered = state or "missing"
            return Decision(
                "pending",
                f"Required check {context} is {rendered}",
                (f"pending-check:{context}",),
            )

    evidence = parse_evidence_body(
        snapshot.body,
        head_sha=snapshot.head_sha,
        policy=policy,
        evidence_url=snapshot.html_url,
    )
    if evidence is None:
        return Decision(
            "pending",
            "Current-head structured evidence is required in the pull request body",
            ("missing-evidence-body",),
        )

    authorized = set(
        _string_list(policy.get("authorized_associations"), field="authorized_associations")
    )
    if snapshot.author_association.upper() in authorized:
        if evidence.reviewer.lower() != snapshot.author_login.lower():
            return Decision(
                "pending",
                "Solo-maintainer evidence reviewer must match the pull-request author",
                ("solo-reviewer-mismatch",),
            )
        return Decision(
            "success",
            "Elevated solo-maintainer evidence is current and required checks passed",
            (evidence.evidence_url,) if evidence.evidence_url else (),
        )

    latest_reviews = _latest_reviews_by_author(snapshot.reviews)
    reviewer = latest_reviews.get(evidence.reviewer.lower())
    if (
        reviewer is None
        or reviewer.state.upper() != "APPROVED"
        or reviewer.commit_id.lower() != snapshot.head_sha.lower()
        or reviewer.author_login.lower() == snapshot.author_login.lower()
        or reviewer.author_association.upper() not in authorized
    ):
        return Decision(
            "pending",
            "External-contributor elevated changes require current-head authorized approval",
            ("missing-current-approval",),
        )

    return Decision(
        "success",
        "Elevated external-contributor evidence and current-head approval are valid",
        tuple(filter(None, (evidence.evidence_url, reviewer.html_url))),
    )


_MANDATORY_RULESET_CHECKS = {
    "ci-required",
    "security-required",
    "dependency-review",
    "codeql-required",
}
_SAFE_WORKFLOW_MARKERS = (
    "pull_request_target:",
    "zizmor: ignore[dangerous-triggers]",
    "base-only metadata gate",
    "contents: read",
    "pull-requests: read",
    "checks: read",
    "statuses: write",
    "persist-credentials: false",
    "ref: ${{ github.event.pull_request.base.sha }}",
    "python scripts/check_review_evidence.py",
)
_FORBIDDEN_WORKFLOW_MARKERS = (
    "workflow_run:",
    "issue_comment:",
    "pull_request_review_comment:",
    "pull_request.head.ref",
    "github.event.pull_request.head.sha",
    "github.head_ref",
    "refs/pull",
    "gh pr checkout",
)

_TEMPLATE_FIELDS = (
    "Head SHA:",
    "Reviewer:",
    "Risk assessment:",
    "Validation evidence:",
    "Bot/agent findings:",
    "Residual risk:",
)


def _read_contract_file(root: Path, relative: str, failures: list[str]) -> str:
    path = root / relative
    if not path.is_file():
        failures.append(f"Missing review evidence contract file: {relative}")
        return ""
    return path.read_text(encoding="utf-8")


def _ruleset_contract(raw: str, failures: list[str]) -> tuple[set[str], dict[str, object]]:
    try:
        policy = json.loads(raw)
    except json.JSONDecodeError as exc:
        failures.append(f"Tracked main ruleset is invalid JSON: {exc}")
        return set(), {}
    if not isinstance(policy, dict):
        failures.append("Tracked main ruleset must be a JSON object")
        return set(), {}
    rules = policy.get("rules")
    if not isinstance(rules, list):
        failures.append("Tracked main ruleset is missing rules")
        return set(), cast(dict[str, object], policy)
    status_contexts: set[str] = set()
    pull_parameters: dict[str, object] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("type") == "required_status_checks":
            parameters = rule.get("parameters")
            if not isinstance(parameters, dict):
                continue
            checks = parameters.get("required_status_checks")
            if isinstance(checks, list):
                for check in checks:
                    if isinstance(check, dict) and isinstance(check.get("context"), str):
                        status_contexts.add(cast(str, check["context"]))
        if rule.get("type") == "pull_request" and isinstance(rule.get("parameters"), dict):
            pull_parameters = cast(dict[str, object], rule["parameters"])
    return status_contexts, pull_parameters


def validate_repository(root: Path = ROOT) -> list[str]:
    """Validate workflow, policy, template, docs, Taskfile, and ruleset drift."""
    failures: list[str] = []
    policy_path = root / ".github" / "review-evidence-policy.json"
    try:
        policy = load_policy(policy_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"Review evidence policy is invalid: {exc}"]

    context = cast(str, policy["status_context"])
    marker = cast(str, policy["evidence_marker"])
    activation = cast(str, policy["ruleset_activation"])
    required_checks = set(_string_list(policy.get("required_checks"), field="required_checks"))
    expected_checks = _MANDATORY_RULESET_CHECKS | {"Review Threads"}
    if required_checks != expected_checks:
        failures.append(
            "Review evidence required_checks must remain " + ", ".join(sorted(expected_checks))
        )

    workflow = _read_contract_file(root, ".github/workflows/review-evidence-gate.yml", failures)
    thread_workflow = _read_contract_file(
        root, ".github/workflows/review-thread-gate.yml", failures
    )
    if "types: [opened, synchronize, reopened, ready_for_review]" not in thread_workflow:
        failures.append(
            "Review Thread Gate must emit its status when a ready pull request is opened"
        )
    for required in _SAFE_WORKFLOW_MARKERS:
        if required not in workflow:
            failures.append(f"Review evidence workflow missing safe marker: {required}")
    for forbidden in _FORBIDDEN_WORKFLOW_MARKERS:
        if forbidden in workflow:
            failures.append(
                f"Review evidence workflow references untrusted PR head content: {forbidden}"
            )
    template = _read_contract_file(root, ".github/PULL_REQUEST_TEMPLATE.md", failures)
    if marker not in template:
        failures.append(f"Pull request template missing {marker}")
    for field in _TEMPLATE_FIELDS:
        if field not in template:
            failures.append(f"Pull request template missing evidence field: {field}")
    template_lower = template.lower()
    if "edit" not in template_lower or "pull request body" not in template_lower:
        failures.append(
            "Pull request template must instruct authors to edit evidence in the pull request body"
        )
    if "new pull request comment" in template_lower:
        failures.append("Pull request template must not use comments as review evidence")

    public_policy = _read_contract_file(root, "docs/elevated-review-policy.md", failures)
    branch_docs = _read_contract_file(root, "docs/branch-protection.md", failures)
    taskfile = _read_contract_file(root, "Taskfile.yml", failures)
    categories = {
        cast(str, entry["category"])
        for entry in cast(list[dict[str, object]], policy["sensitive_paths"])
    }
    for phrase in (
        context,
        marker,
        "solo-maintainer",
        "external-contributor",
        "current head SHA",
        "bot/agent",
        "pull_request_target",
        "base-only metadata gate",
        "Zizmor",
        "statuses: write",
        *sorted(categories),
        *sorted(required_checks),
    ):
        if phrase not in public_policy:
            failures.append(f"Elevated review policy docs missing: {phrase}")
    if activation not in public_policy or activation not in branch_docs:
        failures.append(
            f"Review evidence activation phase {activation} is not synchronized in docs"
        )
    if context not in branch_docs:
        failures.append(f"Branch protection docs missing review status context: {context}")
    if "python scripts/check_review_evidence.py --validate-repository" not in taskfile:
        failures.append("Taskfile docs gate is missing review evidence repository validation")

    ruleset_raw = _read_contract_file(root, ".github/rulesets/main.json", failures)
    status_contexts, pull_parameters = _ruleset_contract(ruleset_raw, failures)
    missing_existing = _MANDATORY_RULESET_CHECKS - status_contexts
    if missing_existing:
        failures.append(
            "Tracked main ruleset lost existing required checks: "
            + ", ".join(sorted(missing_existing))
        )
    if activation == "bootstrap" and context in status_contexts:
        failures.append(
            f"Bootstrap review policy must not require {context} before workflow activation"
        )
    if activation == "active" and context not in status_contexts:
        failures.append(f"Active review policy ruleset is missing {context}")
    if pull_parameters.get("required_approving_review_count") != 0:
        failures.append("Solo-maintainer ruleset approval count must remain 0")
    if pull_parameters.get("required_review_thread_resolution") is not True:
        failures.append("Main ruleset must continue requiring review-thread resolution")
    try:
        ruleset_policy = json.loads(ruleset_raw)
    except json.JSONDecodeError:
        ruleset_policy = {}
    if isinstance(ruleset_policy, dict) and ruleset_policy.get("bypass_actors") != []:
        failures.append("Main ruleset must not define bypass actors")

    return failures


class ReviewEvidenceClient(Protocol):
    """Minimal client contract used by the policy runtime."""

    def fetch_snapshot(
        self,
        repository: str,
        number: int,
        required_checks: tuple[str, ...],
    ) -> PullRequestSnapshot:
        """Fetch the immutable metadata used by the review policy."""
        ...

    def create_status(
        self,
        repository: str,
        sha: str,
        context: str,
        decision: Decision,
        target_url: str,
    ) -> None:
        """Publish the decision on the pull-request head commit."""
        ...


def resolve_pull_request_number(event: Mapping[str, object]) -> int | None:
    """Resolve a pull-request number from a standard pull_request event."""
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        return None
    number = pull_request.get("number")
    return number if isinstance(number, int) else None


def run_for_pull_request(
    *,
    client: ReviewEvidenceClient,
    repository: str,
    number: int,
    policy: Mapping[str, object],
) -> Decision:
    """Fetch metadata, evaluate policy, and publish the head commit status."""
    required_checks = tuple(_string_list(policy.get("required_checks"), field="required_checks"))
    snapshot = client.fetch_snapshot(repository, number, required_checks)
    decision = evaluate_review_evidence(snapshot, policy)
    context = policy.get("status_context")
    if not isinstance(context, str):
        raise ValueError("Policy field status_context must be a string")
    target_url = f"https://github.com/{repository}/pull/{number}"
    client.create_status(
        repository,
        snapshot.head_sha,
        context,
        decision,
        target_url,
    )
    return decision


class GitHubApiClient:
    """Small standard-library GitHub client for metadata-only policy evaluation."""

    def __init__(self, token: str, *, api_url: str = "https://api.github.com") -> None:
        if not token:
            raise ValueError("GitHub token must not be empty")
        self._token = token
        self._api_url = api_url.rstrip("/")

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, object] | None = None,
        accept: str = "application/vnd.github+json",
    ) -> object:
        url = path if path.startswith("https://") else f"{self._api_url}{path}"
        parsed_url = urllib.parse.urlparse(url)
        if parsed_url.scheme != "https" or not parsed_url.netloc:
            raise ValueError("GitHub API requests must use an absolute HTTPS URL")
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(  # noqa: S310 - URL is validated above.
            url,
            data=data,
            method=method,
            headers={
                "Accept": accept,
                "Authorization": f"Bearer {self._token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "fovux-review-evidence-gate",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"GitHub API {method} {path} failed: {exc.code} {detail}") from exc
        if not body:
            return None
        return json.loads(body)

    def _mapping(self, path: str) -> dict[str, object]:
        payload = self._request("GET", path)
        if not isinstance(payload, dict):
            raise RuntimeError(f"GitHub API response for {path} must be an object")
        return cast(dict[str, object], payload)

    def _paginate(self, path: str) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        page = 1
        while True:
            separator = "&" if "?" in path else "?"
            payload = self._request("GET", f"{path}{separator}per_page=100&page={page}")
            if not isinstance(payload, list):
                raise RuntimeError(f"GitHub API response for {path} must be a list")
            page_items = [
                cast(dict[str, object], item) for item in payload if isinstance(item, dict)
            ]
            items.extend(page_items)
            if len(payload) < 100:
                return items
            page += 1

    def _check_runs(self, repository: str, sha: str) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        page = 1
        while True:
            payload = self._mapping(
                f"/repos/{repository}/commits/{sha}/check-runs?per_page=100&page={page}"
            )
            raw_runs = payload.get("check_runs")
            if not isinstance(raw_runs, list):
                raise RuntimeError("GitHub check-runs response is missing check_runs")
            page_items = [
                cast(dict[str, object], item) for item in raw_runs if isinstance(item, dict)
            ]
            items.extend(page_items)
            if len(raw_runs) < 100:
                return items
            page += 1

    def _unresolved_threads(self, repository: str, number: int) -> int:
        owner, repo = repository.split("/", 1)
        query = """
          query($owner: String!, $repo: String!, $number: Int!, $cursor: String) {
            repository(owner: $owner, name: $repo) {
              pullRequest(number: $number) {
                reviewThreads(first: 100, after: $cursor) {
                  pageInfo { hasNextPage endCursor }
                  nodes { isResolved isOutdated }
                }
              }
            }
          }
        """
        cursor: str | None = None
        unresolved = 0
        while True:
            response = self._request(
                "POST",
                "/graphql",
                payload={
                    "query": query,
                    "variables": {
                        "owner": owner,
                        "repo": repo,
                        "number": number,
                        "cursor": cursor,
                    },
                },
            )
            if not isinstance(response, dict):
                raise RuntimeError("GitHub GraphQL response must be an object")
            errors = response.get("errors")
            if errors:
                raise RuntimeError(f"GitHub GraphQL review-thread query failed: {errors}")
            data = response.get("data")
            if not isinstance(data, dict):
                raise RuntimeError("GitHub GraphQL response is missing data")
            repository_data = data.get("repository")
            if not isinstance(repository_data, dict):
                raise RuntimeError("GitHub GraphQL response is missing repository")
            pull_request = repository_data.get("pullRequest")
            if not isinstance(pull_request, dict):
                raise RuntimeError("GitHub GraphQL response is missing pullRequest")
            threads = pull_request.get("reviewThreads")
            if not isinstance(threads, dict):
                raise RuntimeError("GitHub GraphQL response is missing reviewThreads")
            nodes = threads.get("nodes")
            if not isinstance(nodes, list):
                raise RuntimeError("GitHub GraphQL response is missing review thread nodes")
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                if node.get("isResolved") is False and node.get("isOutdated") is not True:
                    unresolved += 1
            page_info = threads.get("pageInfo")
            if not isinstance(page_info, dict) or page_info.get("hasNextPage") is not True:
                return unresolved
            next_cursor = page_info.get("endCursor")
            if not isinstance(next_cursor, str) or not next_cursor:
                raise RuntimeError("GitHub GraphQL pagination cursor is missing")
            cursor = next_cursor

    @staticmethod
    def _login(item: Mapping[str, object]) -> str:
        user = item.get("user")
        if not isinstance(user, dict):
            return ""
        login = user.get("login")
        return login if isinstance(login, str) else ""

    def fetch_snapshot(
        self,
        repository: str,
        number: int,
        required_checks: tuple[str, ...],
    ) -> PullRequestSnapshot:
        """Fetch all immutable and review metadata needed by the policy engine."""
        pull_request = self._mapping(f"/repos/{repository}/pulls/{number}")
        head = pull_request.get("head")
        user = pull_request.get("user")
        if not isinstance(head, dict) or not isinstance(user, dict):
            raise RuntimeError("Pull-request response is missing head or user metadata")
        head_sha = head.get("sha")
        author_login = user.get("login")
        author_association = pull_request.get("author_association")
        body = pull_request.get("body")
        html_url = pull_request.get("html_url")
        if not all(
            isinstance(value, str)
            for value in (head_sha, author_login, author_association, html_url)
        ):
            raise RuntimeError("Pull-request identity metadata is invalid")
        if body is not None and not isinstance(body, str):
            raise RuntimeError("Pull-request body metadata is invalid")

        labels_raw = pull_request.get("labels")
        labels: list[str] = []
        if isinstance(labels_raw, list):
            for label in labels_raw:
                if isinstance(label, dict) and isinstance(label.get("name"), str):
                    labels.append(cast(str, label["name"]))

        files = tuple(
            filename
            for item in self._paginate(f"/repos/{repository}/pulls/{number}/files")
            if isinstance((filename := item.get("filename")), str)
        )
        reviews = tuple(
            Review(
                author_login=self._login(item),
                author_association=str(item.get("author_association") or "NONE"),
                state=str(item.get("state") or ""),
                commit_id=str(item.get("commit_id") or ""),
                html_url=str(item.get("html_url") or ""),
            )
            for item in self._paginate(f"/repos/{repository}/pulls/{number}/reviews")
        )

        context_states: dict[str, str] = {}
        combined = self._mapping(f"/repos/{repository}/commits/{head_sha}/status")
        statuses = combined.get("statuses")
        if isinstance(statuses, list):
            for item in statuses:
                if not isinstance(item, dict):
                    continue
                context = item.get("context")
                state = item.get("state")
                if isinstance(context, str) and isinstance(state, str):
                    context_states.setdefault(context, state)
        for item in self._check_runs(repository, cast(str, head_sha)):
            name = item.get("name")
            status = item.get("status")
            conclusion = item.get("conclusion")
            if not isinstance(name, str):
                continue
            state = str(conclusion or "pending") if status == "completed" else "pending"
            context_states.setdefault(name, state)

        checks = tuple(
            CheckContext(context, context_states[context])
            for context in required_checks
            if context in context_states
        )
        return PullRequestSnapshot(
            number=number,
            head_sha=cast(str, head_sha),
            author_login=cast(str, author_login),
            author_association=cast(str, author_association),
            labels=tuple(sorted(set(labels))),
            files=tuple(sorted(set(files))),
            body=body or "",
            html_url=cast(str, html_url),
            reviews=reviews,
            checks=checks,
            unresolved_threads=self._unresolved_threads(repository, number),
        )

    def create_status(
        self,
        repository: str,
        sha: str,
        context: str,
        decision: Decision,
        target_url: str,
    ) -> None:
        """Write the policy decision as a commit status on the PR head."""
        self._request(
            "POST",
            f"/repos/{repository}/statuses/{sha}",
            payload={
                "state": decision.state,
                "context": context,
                "description": decision.description[:140],
                "target_url": target_url,
            },
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY_PATH)
    parser.add_argument("--validate-repository", action="store_true")
    parser.add_argument("--event-path", type=Path)
    parser.add_argument("--repository")
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate policy locally or evaluate one GitHub metadata event."""
    args = build_parser().parse_args(argv)
    policy = load_policy(args.policy)
    if args.validate_repository:
        failures = validate_repository(ROOT)
        if failures:
            for failure in failures:
                print(f"ERROR: {failure}")
            return 1
        print("Elevated review repository contract is synchronized.")
        return 0
    if args.event_path is None:
        print("Elevated review policy is valid.")
        return 0
    if not args.repository:
        raise SystemExit("--repository is required with --event-path")
    event_raw = json.loads(args.event_path.read_text(encoding="utf-8"))
    if not isinstance(event_raw, dict):
        raise SystemExit("GitHub event payload must be a JSON object")
    number = resolve_pull_request_number(cast(dict[str, object], event_raw))
    if number is None:
        print("SKIP: metadata event is not associated with a pull request")
        return 0
    token = os.environ.get(args.token_env, "")
    if not token:
        raise SystemExit(f"{args.token_env} is required for GitHub evaluation")
    decision = run_for_pull_request(
        client=GitHubApiClient(token),
        repository=args.repository,
        number=number,
        policy=policy,
    )
    print(f"{decision.state.upper()}: {decision.description}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
