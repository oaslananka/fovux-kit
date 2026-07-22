from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "check_docs_truth.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_docs_truth", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clear_github_context(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "GITHUB_EVENT_NAME",
        "GITHUB_HEAD_REF",
        "GITHUB_REF",
        "GITHUB_REF_NAME",
    ):
        monkeypatch.delenv(name, raising=False)


def test_release_please_branch_allows_candidate_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    _clear_github_context(monkeypatch)
    monkeypatch.setenv("GITHUB_HEAD_REF", "release-please--branches--main")

    assert module._is_release_candidate_context(commit_subject="ordinary commit")


def test_exact_release_commit_on_main_allows_candidate_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module()
    _clear_github_context(monkeypatch)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
    monkeypatch.setenv("GITHUB_REF_NAME", "main")

    assert module._is_release_candidate_context(commit_subject="chore(release): release (#188)")


@pytest.mark.parametrize(
    ("event_name", "ref_name", "subject"),
    [
        ("push", "main", "docs: leave candidate metadata behind"),
        ("workflow_dispatch", "main", "chore(release): release (#188)"),
        ("pull_request", "feature/release", "chore(release): release (#188)"),
        ("push", "main", "chore(release): release"),
        ("push", "main", "chore(release): release (#not-a-number)"),
    ],
)
def test_unrelated_contexts_require_published_baseline(
    monkeypatch: pytest.MonkeyPatch,
    event_name: str,
    ref_name: str,
    subject: str,
) -> None:
    module = _load_module()
    _clear_github_context(monkeypatch)
    monkeypatch.setenv("GITHUB_EVENT_NAME", event_name)
    monkeypatch.setenv("GITHUB_REF_NAME", ref_name)

    assert not module._is_release_candidate_context(commit_subject=subject)
