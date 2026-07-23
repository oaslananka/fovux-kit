"""Architecture constraints for the decomposed run registry."""

from __future__ import annotations

import ast
from pathlib import Path

from sqlalchemy import inspect

from fovux.core.run_registry.database import RegistryDatabase
from fovux.core.run_registry.models import Base, RunRecord

CORE = Path(__file__).resolve().parents[3] / "src" / "fovux" / "core"
LOW_LEVEL_MODULES = {
    "models.py",
    "database.py",
    "lifecycle.py",
    "metadata.py",
    "events.py",
    "run_repository.py",
    "operation_repository.py",
    "artifact_repository.py",
    "catalog_repository.py",
}


def test_database_creates_existing_schema_names(tmp_path: Path) -> None:
    """The new database boundary must preserve all existing table names."""
    database = RegistryDatabase(tmp_path / "runs.db")
    try:
        tables = set(inspect(database.engine).get_table_names())
    finally:
        database.close()

    assert RunRecord.__table__.metadata is Base.metadata
    assert {
        "runs",
        "operations",
        "operation_events",
        "schema_migrations",
        "run_events",
        "datasets",
        "artifacts",
        "models",
        "exports",
        "review_queue",
        "metrics",
        "tags",
        "audit_events",
    } <= tables


def test_lower_level_registry_modules_do_not_import_facade_or_compatibility_module() -> None:
    """Implementation dependencies must point inward, never back to the facade."""
    package = CORE / "run_registry"
    violations: list[str] = []
    for path in sorted(package.glob("*.py")):
        if path.name not in LOW_LEVEL_MODULES:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module in {"fovux.core.runs", "fovux.core.run_registry.facade"}:
                    violations.append(f"{path.name}:{node.lineno}:{module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {"fovux.core.runs", "fovux.core.run_registry.facade"}:
                        violations.append(f"{path.name}:{node.lineno}:{alias.name}")

    assert violations == []
