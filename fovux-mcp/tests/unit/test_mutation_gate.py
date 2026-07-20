"""Contract tests for the focused mutation-testing gate."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path
from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_mutation_stats.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "mutation.yml"
PYPROJECT_PATH = REPO_ROOT / "fovux-mcp" / "pyproject.toml"

EXPECTED_MUTATION_TARGETS = {
    "src/fovux/core/path_policy.py",
    "src/fovux/core/tool_registry.py",
    "src/fovux/http/challenge.py",
}


def _load_module() -> ModuleType:
    assert SCRIPT_PATH.exists(), "mutation stats checker is missing"
    spec = importlib.util.spec_from_file_location("check_mutation_stats", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mutmut_config_uses_focused_v3_contract() -> None:
    config = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))["tool"]["mutmut"]

    assert "paths_to_mutate" not in config
    assert config["source_paths"] == ["src/fovux"]
    assert set(config["only_mutate"]) == EXPECTED_MUTATION_TARGETS
    assert config["mutate_only_covered_lines"] is True
    assert config["pytest_add_cli_args_test_selection"] == [
        "tests/unit/test_path_policy.py",
        "tests/unit/test_tool_registry.py::test_available_tools_lists_known_entries",
        "tests/unit/test_tool_registry.py::test_list_tool_names_is_available_tools_alias",
        "tests/unit/test_tool_registry.py::test_resolve_tool_unknown_name_raises_key_error",
        "tests/unit/test_tool_registry.py::test_register_all_imports_all_tool_modules",
        "tests/unit/test_http_challenge.py::TestChallengeUnit",
    ]


def test_mutation_stats_reject_zero_evaluated_mutants() -> None:
    module = _load_module()
    stats = {
        "killed": 0,
        "survived": 0,
        "total": 0,
        "no_tests": 0,
        "skipped": 0,
        "suspicious": 0,
        "timeout": 0,
        "check_was_interrupted_by_user": False,
        "segfault": 0,
    }

    summary, failures = module.evaluate_stats(
        stats,
        minimum_score=70.0,
        max_survived=10,
        max_timeouts=0,
    )

    assert summary["evaluated"] == 0
    assert any("No mutants were evaluated" in failure for failure in failures)


def test_mutation_stats_enforce_score_and_exception_budgets() -> None:
    module = _load_module()
    stats = {
        "killed": 70,
        "survived": 12,
        "total": 85,
        "no_tests": 1,
        "skipped": 0,
        "suspicious": 1,
        "timeout": 1,
        "check_was_interrupted_by_user": False,
        "segfault": 0,
    }

    summary, failures = module.evaluate_stats(
        stats,
        minimum_score=85.0,
        max_survived=10,
        max_timeouts=0,
    )

    assert summary["score"] < 85.0
    assert any("mutation score" in failure.lower() for failure in failures)
    assert any("survived" in failure for failure in failures)
    assert any("timed out" in failure for failure in failures)
    assert any("no test coverage" in failure for failure in failures)
    assert any("suspicious" in failure for failure in failures)


def test_mutation_workflow_exports_and_checks_machine_readable_stats() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    assert "python ../scripts/run_mutmut.py run --max-children 2" in workflow
    assert "python ../scripts/run_mutmut.py export-cicd-stats" in workflow
    assert "python ../scripts/check_mutation_stats.py" in workflow
    assert "mutants/mutmut-cicd-stats.json" in workflow
    assert "mutation-results.txt" in workflow
    assert "minimum-score 50" in workflow
    assert "max-survived 120" in workflow
    assert 'PY_KEY_VALUE_DISABLE_BEARTYPE: "true"' in workflow
    assert "find src tests -type d -exec chmod u+rwx,g-s" in workflow


def test_mutmut_wrapper_preloads_multiprocessing_before_mutmut() -> None:
    wrapper = (REPO_ROOT / "scripts" / "run_mutmut.py").read_text(encoding="utf-8")

    assert wrapper.index("_preload_multiprocessing()") < wrapper.index(
        "from mutmut.__main__ import cli"
    )
    assert 'multiprocessing.get_context("fork")' in wrapper
    assert "context.Pool(processes=1)" in wrapper
    assert wrapper.index("_disable_optional_dependency_import_hook()") < wrapper.index(
        "from mutmut.__main__ import cli"
    )
    assert "beartype.claw.beartype_this_package = no_op_hook" in wrapper
    assert wrapper.index("import pytest") < wrapper.index("from mutmut.__main__ import cli")
