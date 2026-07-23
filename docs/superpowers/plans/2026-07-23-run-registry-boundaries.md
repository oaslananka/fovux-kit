# Run Registry Boundary Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose the 1,176-line SQLite run registry into cohesive, directly testable modules while preserving the complete `fovux.core.runs` public API and persisted SQLite semantics.

**Architecture:** `fovux.core.runs` remains a compatibility module and process-local singleton cache. A composed `RunRegistry` facade delegates to repositories sharing one `RegistryDatabase` session factory; repositories depend on lifecycle, metadata, and event helpers, which depend only on database/models.

**Tech Stack:** Python 3.12+, SQLAlchemy 2.x, SQLite WAL, pytest 9, Ruff, strict mypy 2.1, GitHub Actions.

## Global Constraints

- Existing imports from `fovux.core.runs` must continue to work.
- Existing ORM table names, column names, indexes, defaults, JSON encodings, and migration version must remain unchanged.
- Existing databases must migrate in place without destructive or copy migrations.
- SQLite remains the only registry backend.
- Existing `RunRegistry` method names, positional argument order, defaults, missing-record behavior, and returned ORM types remain stable.
- Run creation plus lineage plus initial event is one transaction.
- Run status plus transition event plus audit event is one transaction.
- Filesystem hashing and metadata inspection complete before a database write transaction opens.
- HTTP operation event persistence and live fan-out preserve the exactly-once event contract from #171.
- Lower-level `run_registry` modules must never import `fovux.core.runs` or `run_registry.facade`.
- No MCP tool, HTTP route, Studio message, or public configuration contract changes.

---

### Task 1: Lock Import Direction and Extract ORM/Database Infrastructure

**Files:**
- Create: `fovux-mcp/src/fovux/core/run_registry/__init__.py`
- Create: `fovux-mcp/src/fovux/core/run_registry/models.py`
- Create: `fovux-mcp/src/fovux/core/run_registry/database.py`
- Create: `fovux-mcp/tests/unit/core/test_run_registry_architecture.py`
- Modify later, not in this task: `fovux-mcp/src/fovux/core/runs.py`

**Interfaces:**
- Produces: `Base`, `UtcDateTime`, `_utcnow_naive()`, `_serialize_datetime()`, `_deserialize_datetime()`, and all existing ORM record classes from `models.py`.
- Produces: `RegistryDatabase(db_path: Path)`, `.session_factory: sessionmaker[Session]`, and `.close() -> None` from `database.py`.
- Consumes: no new project modules except `run_registry.models` from `database.py`.

- [ ] **Step 1: Write the failing architecture and schema-identity tests**

Create `fovux-mcp/tests/unit/core/test_run_registry_architecture.py` with:

```python
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
```

- [ ] **Step 2: Run the new test and verify RED**

Run:

```bash
cd fovux-mcp
../.venv/bin/python -m pytest tests/unit/core/test_run_registry_architecture.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'fovux.core.run_registry'`.

- [ ] **Step 3: Move ORM declarations without changing schema**

Create `run_registry/models.py` by moving these existing symbols verbatim from `fovux.core.runs`:

```python
_utcnow_naive
_serialize_datetime
_deserialize_datetime
UtcDateTime
Base
RunRecord
OperationRecord
OperationEventRecord
SchemaMigrationRecord
RunEventRecord
DatasetRecord
ArtifactRecord
ModelRecord
ExportRecord
ReviewQueueEntry
MetricRecord
TagRecord
AuditEventRecord
```

Keep the same SQLAlchemy column declarations, table names, defaults, indexes, and comments. Export them explicitly:

```python
__all__ = [
    "ArtifactRecord",
    "AuditEventRecord",
    "Base",
    "DatasetRecord",
    "ExportRecord",
    "MetricRecord",
    "ModelRecord",
    "OperationEventRecord",
    "OperationRecord",
    "ReviewQueueEntry",
    "RunEventRecord",
    "RunRecord",
    "SchemaMigrationRecord",
    "TagRecord",
    "UtcDateTime",
    "_deserialize_datetime",
    "_serialize_datetime",
    "_utcnow_naive",
]
```

- [ ] **Step 4: Implement the database boundary**

Create `run_registry/database.py` with this public shape:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from fovux.core.run_registry.models import Base, _serialize_datetime, _utcnow_naive


class RegistryDatabase:
    """Own the SQLite engine, schema bootstrap, migrations, and session factory."""

    def __init__(self, db_path: Path) -> None:
        self.engine: Engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            poolclass=NullPool,
            connect_args={"check_same_thread": False},
        )
        event.listen(self.engine, "connect", self._set_sqlite_pragmas)
        Base.metadata.create_all(self.engine)
        self._run_migrations()
        self.session_factory: sessionmaker[Session] = sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    @staticmethod
    def _set_sqlite_pragmas(
        dbapi_conn: sqlite3.Connection,
        _connection_record: object,
    ) -> None:
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        self.engine.dispose()
```

Move `_run_migrations()` and `_apply_migration_1()` from the monolith unchanged into this class. Use `self.engine.begin()` and preserve migration version `1`.

- [ ] **Step 5: Export the infrastructure package**

Create `run_registry/__init__.py`:

```python
"""Internal SQLite run-registry implementation boundaries."""

from fovux.core.run_registry.database import RegistryDatabase
from fovux.core.run_registry.models import *  # noqa: F403

__all__ = ["RegistryDatabase"]
```

Do not import the facade from this package root yet; this prevents cycles during incremental extraction.

- [ ] **Step 6: Run focused tests and static checks**

Run:

```bash
cd fovux-mcp
../.venv/bin/python -m pytest tests/unit/core/test_run_registry_architecture.py -q
../.venv/bin/ruff check src/fovux/core/run_registry tests/unit/core/test_run_registry_architecture.py
../.venv/bin/ruff format --check src/fovux/core/run_registry tests/unit/core/test_run_registry_architecture.py
../.venv/bin/mypy src/fovux/core/run_registry/models.py src/fovux/core/run_registry/database.py --strict
```

Expected: architecture tests pass; Ruff and mypy report no errors.

- [ ] **Step 7: Commit the infrastructure boundary**

```bash
git add fovux-mcp/src/fovux/core/run_registry fovux-mcp/tests/unit/core/test_run_registry_architecture.py
git commit -m "refactor(registry): extract schema and database boundary"
```

---

### Task 2: Centralize Run and Operation Lifecycle Policy

**Files:**
- Create: `fovux-mcp/src/fovux/core/run_registry/lifecycle.py`
- Create: `fovux-mcp/tests/unit/core/test_run_registry_lifecycle.py`

**Interfaces:**
- Produces: `RunStatus`, `OperationStatus`, `RUN_TERMINAL_STATUSES`, `OPERATION_TERMINAL_STATUSES`.
- Produces: `RunLifecyclePolicy.apply(record: RunRecord, target: RunStatus, *, pid: int | None, now: datetime) -> bool`.
- Produces: `OperationLifecyclePolicy.apply(record: OperationRecord, target: OperationStatus, *, now: datetime) -> bool`.
- The boolean return is `True` only when the status value changed; repositories use it to decide whether to append transition events.

- [ ] **Step 1: Write failing policy tests**

Create tests that instantiate ORM records without a database:

```python
from datetime import datetime

import pytest

from fovux.core.run_registry.lifecycle import (
    OperationLifecyclePolicy,
    RunLifecyclePolicy,
)
from fovux.core.run_registry.models import OperationRecord, RunRecord

NOW = datetime(2026, 7, 23, 12, 0, 0)


def _run(status: str = "pending") -> RunRecord:
    return RunRecord(
        id="run_policy",
        status=status,
        model="yolo.pt",
        dataset_path="dataset",
        task="detect",
        epochs=1,
        run_path="runs/run_policy",
        tags_json="[]",
        extra_json="{}",
    )


def _operation(status: str = "pending") -> OperationRecord:
    return OperationRecord(
        id="op_policy",
        tool="model_list",
        arguments_json="{}",
        status=status,
    )


def test_run_policy_applies_timestamps_and_pid() -> None:
    record = _run()
    assert RunLifecyclePolicy.apply(record, "running", pid=42, now=NOW) is True
    assert record.status == "running"
    assert record.pid == 42
    assert record.started_at == NOW
    assert record.finished_at is None


def test_run_policy_rejects_invalid_transition_without_mutation() -> None:
    record = _run("complete")
    with pytest.raises(ValueError, match="Invalid run status transition"):
        RunLifecyclePolicy.apply(record, "pending", pid=None, now=NOW)
    assert record.status == "complete"
    assert record.finished_at is None


def test_operation_policy_rejects_terminal_rewrite() -> None:
    record = _operation("succeeded")
    with pytest.raises(ValueError, match="Invalid operation status transition"):
        OperationLifecyclePolicy.apply(record, "failed", now=NOW)
    assert record.status == "succeeded"


def test_same_state_is_not_a_transition() -> None:
    record = _operation("running")
    assert OperationLifecyclePolicy.apply(record, "running", now=NOW) is False
```

- [ ] **Step 2: Run tests and verify RED**

Expected: import failure for `run_registry.lifecycle`.

- [ ] **Step 3: Implement exact transition maps and timestamp rules**

Create `lifecycle.py` with:

```python
RunStatus = Literal["pending", "running", "complete", "failed", "stopped", "archived"]
OperationStatus = Literal["pending", "running", "succeeded", "failed", "cancelled"]

RUN_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "pending": frozenset({"running", "complete", "failed", "stopped", "archived"}),
    "running": frozenset({"complete", "failed", "stopped", "archived"}),
    "complete": frozenset({"running", "archived"}),
    "failed": frozenset({"running", "archived"}),
    "stopped": frozenset({"running", "archived"}),
    "archived": frozenset({"pending", "running"}),
}

OPERATION_TRANSITIONS: Final[dict[str, frozenset[str]]] = {
    "pending": frozenset({"running", "failed", "cancelled"}),
    "running": frozenset({"succeeded", "failed", "cancelled"}),
    "succeeded": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}
```

`RunLifecyclePolicy.apply()` must validate before assignment, set `started_at` only on the first transition to `running`, set `finished_at` for `complete|failed|stopped|archived`, and apply a non-`None` PID even on same-state updates. `OperationLifecyclePolicy.apply()` must set `started_at` on first `running` and `finished_at` for terminal states.

- [ ] **Step 4: Run policy tests, Ruff, and mypy**

Expected: all lifecycle tests pass and no static errors.

- [ ] **Step 5: Commit lifecycle policy**

```bash
git add fovux-mcp/src/fovux/core/run_registry/lifecycle.py fovux-mcp/tests/unit/core/test_run_registry_lifecycle.py
git commit -m "refactor(registry): centralize lifecycle policy"
```

---

### Task 3: Extract Metadata and Durable Event Store

**Files:**
- Create: `fovux-mcp/src/fovux/core/run_registry/metadata.py`
- Create: `fovux-mcp/src/fovux/core/run_registry/events.py`
- Create: `fovux-mcp/tests/unit/core/test_run_registry_events.py`
- Create: `fovux-mcp/tests/unit/core/test_run_registry_metadata.py`

**Interfaces:**
- Produces: immutable `RunMetadata(dataset_fingerprint, config_hash, code_version, env_summary)`.
- Produces: immutable `ArtifactMetadata(path: str, sha256: str | None, size: int | None)`.
- Produces: `RunMetadataProvider.build(...)`, `.dataset_class_map(dataset_path: Path)`, and `.artifact_metadata(path: Path, sha256, size)`.
- Produces: `EventStore(session_factory)` with session-aware `append_run_event()`, `append_audit_event()`, standalone `create_operation_event()`, and existing list methods.

- [ ] **Step 1: Write RED tests for fallback metadata and event ordering**

Tests must prove:

```python
metadata = provider.build(
    model="yolo.pt",
    dataset_path=missing_path,
    task="detect",
    epochs=3,
    extra={"batch": 4},
)
assert len(metadata.dataset_fingerprint) == 64
assert len(metadata.config_hash) == 64
assert json.loads(metadata.env_summary)["python_version"]
```

and:

```python
first = store.create_operation_event("op", "status_change", {"status": "pending"})
second = store.create_operation_event("op", "status_change", {"status": "running"})
assert [event.id for event in store.list_operation_events()] == [first.id, second.id]
assert [event.id for event in store.list_operation_events(last_event_id=first.id)] == [second.id]
```

- [ ] **Step 2: Verify RED**

Expected: imports for `metadata` and `events` fail.

- [ ] **Step 3: Move metadata logic behind typed values**

Move `_auto_metadata()` behavior into `RunMetadataProvider.build()`. Move dataset YAML class-map loading into `dataset_class_map()`. Move artifact digest/size inspection from `add_artifact()` into `artifact_metadata()`. Preserve all current exception fallbacks and 65,536-byte hashing chunks.

- [ ] **Step 4: Implement EventStore**

Use `sessionmaker[Session]` injection. Session-aware methods add records but never commit:

```python
@staticmethod
def append_run_event(
    session: Session,
    *,
    run_id: str | None,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    message: str | None,
    extra: dict[str, Any] | None = None,
) -> RunEventRecord:
    ...

@staticmethod
def append_audit_event(
    session: Session,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any],
) -> AuditEventRecord:
    ...
```

Standalone `create_operation_event`, `list_operation_events`, `list_run_events`, `log_audit_event`, and `list_audit_events` preserve current signatures, ordering, limits, and JSON serialization.

- [ ] **Step 5: Run focused tests and static checks**

Expected: metadata and event tests pass; Ruff/mypy clean.

- [ ] **Step 6: Commit metadata and event boundaries**

```bash
git add fovux-mcp/src/fovux/core/run_registry/metadata.py fovux-mcp/src/fovux/core/run_registry/events.py fovux-mcp/tests/unit/core/test_run_registry_events.py fovux-mcp/tests/unit/core/test_run_registry_metadata.py
git commit -m "refactor(registry): extract metadata and event stores"
```

---

### Task 4: Implement the Transactional Run Repository

**Files:**
- Create: `fovux-mcp/src/fovux/core/run_registry/run_repository.py`
- Create: `fovux-mcp/src/fovux/core/run_registry/catalog_repository.py`
- Create: `fovux-mcp/tests/unit/core/test_run_repository_transactions.py`
- Modify: `fovux-mcp/tests/unit/test_lineage_ledger.py`

**Interfaces:**
- Produces: `CatalogRepository.register_lineage(session, *, run_id, model, dataset_path, task, dataset_fingerprint) -> None`.
- Produces: `RunRepository(session_factory, metadata_provider, event_store, catalog_repository)` with the existing run method signatures.
- Consumes: lifecycle policy, metadata provider, event-store session helpers, and ORM models.

- [ ] **Step 1: Write RED transaction rollback tests**

Create a test event store subclass whose `append_audit_event()` raises `RuntimeError("audit unavailable")`. After creating and starting a run, call `repository.update_status(run_id, "complete")` and assert:

```python
with pytest.raises(RuntimeError, match="audit unavailable"):
    repository.update_status("run_tx", "complete")

record = repository.get_run("run_tx")
assert record is not None
assert record.status == "running"
assert [event.to_status for event in event_store.list_run_events("run_tx")] == [
    "pending",
    "running",
]
```

Also create a pre-v1 SQLite schema with an existing `runs` row, initialize `RegistryDatabase`, and assert the row remains readable with newly added nullable lineage columns.

- [ ] **Step 2: Verify RED**

Expected: `RunRepository` and `CatalogRepository` imports fail.

- [ ] **Step 3: Implement CatalogRepository lineage write**

Move `_register_lineage()` behavior into `CatalogRepository.register_lineage()`. It receives the caller's active `Session`, merges dataset/model rows when absent, and does not commit. Move `get_dataset`, `list_datasets`, `add_metric`, `list_metrics`, and review-queue methods into the same repository with their existing semantics.

- [ ] **Step 4: Implement RunRepository**

Move these methods with unchanged public signatures:

```text
reserve_run_slot
create_run
get_run
update_status
list_runs
delete_run
update_tags
update_extra
```

Both create paths must call metadata before `with session.begin()`. Inside the transaction they add `RunRecord`, call `catalog.register_lineage(...)`, and append the initial pending run event. `update_status()` must select the row, return for missing records, call `RunLifecyclePolicy.apply()`, and append transition/audit events only when the returned boolean is `True`.

- [ ] **Step 5: Run repository, lineage, run, and concurrency tests**

```bash
cd fovux-mcp
../.venv/bin/python -m pytest \
  tests/unit/core/test_run_repository_transactions.py \
  tests/unit/test_runs.py \
  tests/unit/test_lineage_ledger.py \
  tests/chaos/test_registry_concurrency.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Run Ruff and strict mypy**

Expected: no issues for the new repository modules and tests.

- [ ] **Step 7: Commit run repository extraction**

```bash
git add fovux-mcp/src/fovux/core/run_registry/run_repository.py fovux-mcp/src/fovux/core/run_registry/catalog_repository.py fovux-mcp/tests/unit/core/test_run_repository_transactions.py fovux-mcp/tests/unit/test_lineage_ledger.py
git commit -m "refactor(registry): isolate transactional run repository"
```

---

### Task 5: Extract Operation and Artifact Repositories

**Files:**
- Create: `fovux-mcp/src/fovux/core/run_registry/operation_repository.py`
- Create: `fovux-mcp/src/fovux/core/run_registry/artifact_repository.py`
- Create: `fovux-mcp/tests/unit/core/test_operation_repository.py`
- Create: `fovux-mcp/tests/unit/core/test_artifact_repository_transactions.py`

**Interfaces:**
- Produces: `OperationRepository` with existing operation CRUD/query signatures.
- Produces: `ArtifactRepository` with existing artifact/export signatures.
- Consumes: `OperationLifecyclePolicy`, `RunMetadataProvider.artifact_metadata()`, `EventStore.append_audit_event()`, and ORM models.

- [ ] **Step 1: Write RED operation policy integration tests**

Create an operation, transition `pending -> running -> succeeded`, then assert terminal rewrite fails and leaves the row unchanged:

```python
repository.update_operation_status("op_tx", "running")
repository.update_operation_status("op_tx", "succeeded", result={"ok": True})
with pytest.raises(ValueError, match="Invalid operation status transition"):
    repository.update_operation_status("op_tx", "failed", error="late failure")
assert repository.get_operation("op_tx").status == "succeeded"
```

Verify missing operation updates remain no-ops and idempotency lookup remains unchanged.

- [ ] **Step 2: Write RED atomic export test**

Inject an event store whose `append_audit_event()` raises. Call `record_export()` and assert neither the export nor associated artifact exists after rollback.

- [ ] **Step 3: Implement OperationRepository**

Move `create_operation`, `get_operation`, `get_operation_by_idempotency_key`, `update_operation_status`, `update_operation_progress`, and `list_operations`. Validate every actual status change through `OperationLifecyclePolicy`; preserve result/error/run ID assignment and missing-record behavior.

- [ ] **Step 4: Implement ArtifactRepository**

Move `add_artifact`, `record_export`, `list_artifacts`, and `list_exports`. Compute `ArtifactMetadata` before opening the transaction. Add a private `_merge_artifact(session, ...)` helper used by both public write methods. `record_export()` writes export, artifact, and audit in one `session.begin()` block.

- [ ] **Step 5: Run focused and existing operation tests**

```bash
cd fovux-mcp
../.venv/bin/python -m pytest \
  tests/unit/core/test_operation_repository.py \
  tests/unit/core/test_artifact_repository_transactions.py \
  tests/unit/http/services/test_operation_service.py \
  tests/unit/test_lineage_ledger.py -q
```

Expected: all pass, including exactly-once operation event tests.

- [ ] **Step 6: Commit operation and artifact boundaries**

```bash
git add fovux-mcp/src/fovux/core/run_registry/operation_repository.py fovux-mcp/src/fovux/core/run_registry/artifact_repository.py fovux-mcp/tests/unit/core/test_operation_repository.py fovux-mcp/tests/unit/core/test_artifact_repository_transactions.py
git commit -m "refactor(registry): isolate operation and artifact repositories"
```

---

### Task 6: Cut Over to the Composed RunRegistry Facade

**Files:**
- Create: `fovux-mcp/src/fovux/core/run_registry/facade.py`
- Replace implementation: `fovux-mcp/src/fovux/core/runs.py`
- Modify: `fovux-mcp/src/fovux/core/run_registry/__init__.py`
- Create: `fovux-mcp/tests/unit/core/test_run_registry_compatibility.py`

**Interfaces:**
- Produces: `RunRegistry(db_path: Path)` with every existing public method and return annotation.
- Preserves: `get_registry(db_path)`, `close_registry(db_path=None)`, `_REGISTRIES`, and `_REGISTRIES_LOCK` in `fovux.core.runs`.
- Re-exports: every former ORM class, `RunStatus`, `OperationStatus`, and datetime helpers from `fovux.core.runs`.

- [ ] **Step 1: Write RED compatibility tests**

Assert object identity, signatures, and singleton behavior:

```python
import inspect

import fovux.core.runs as compatibility
from fovux.core.run_registry.facade import RunRegistry as FacadeRunRegistry
from fovux.core.run_registry.models import RunRecord as ModelRunRecord


def test_compatibility_module_reexports_identical_types() -> None:
    assert compatibility.RunRegistry is FacadeRunRegistry
    assert compatibility.RunRecord is ModelRunRecord


def test_facade_preserves_selected_method_signatures() -> None:
    assert str(inspect.signature(compatibility.RunRegistry.create_run)) == (
        "(self, run_id: 'str', run_path: 'Path', model: 'str', "
        "dataset_path: 'Path', task: 'str', epochs: 'int', "
        "tags: 'list[str] | None' = None, extra: 'dict[str, Any] | None' = None, "
        "dataset_fingerprint: 'str | None' = None, config_hash: 'str | None' = None, "
        "code_version: 'str | None' = None, env_summary: 'str | None' = None, "
        "parent_run_id: 'str | None' = None) -> 'RunRecord'"
    )
```

Keep the existing singleton tests from `test_runs.py` unchanged.

- [ ] **Step 2: Verify RED**

Expected: import failure for `run_registry.facade`.

- [ ] **Step 3: Implement explicit facade composition**

`RunRegistry.__init__()` creates:

```python
self._database = RegistryDatabase(db_path)
self._events = EventStore(self._database.session_factory)
self._metadata = RunMetadataProvider()
self._catalog = CatalogRepository(self._database.session_factory, self._metadata)
self._runs = RunRepository(
    self._database.session_factory,
    metadata_provider=self._metadata,
    event_store=self._events,
    catalog_repository=self._catalog,
)
self._operations = OperationRepository(self._database.session_factory)
self._artifacts = ArtifactRepository(
    self._database.session_factory,
    metadata_provider=self._metadata,
    event_store=self._events,
)
```

Define every public method explicitly and forward to the owning component. Do not use `__getattr__`, inheritance mixins, or dynamic method generation. `close()` calls `self._database.close()`.

- [ ] **Step 4: Replace `fovux.core.runs` with compatibility exports/cache**

The module imports and re-exports models, statuses, and `RunRegistry`, then keeps only:

```python
_REGISTRIES: dict[Path, RunRegistry] = {}
_REGISTRIES_LOCK = threading.Lock()


def get_registry(db_path: Path) -> RunRegistry:
    resolved = db_path.expanduser().resolve()
    with _REGISTRIES_LOCK:
        registry = _REGISTRIES.get(resolved)
        if registry is None:
            registry = RunRegistry(resolved)
            _REGISTRIES[resolved] = registry
        return registry


def close_registry(db_path: Path | None = None) -> None:
    ...
```

Preserve the existing close-one and close-all behavior exactly.

- [ ] **Step 5: Export facade from package root**

Update `run_registry/__init__.py` to export `RegistryDatabase` and `RunRegistry` without wildcard-based public API claims for internal repositories.

- [ ] **Step 6: Run all registry-adjacent tests**

```bash
cd fovux-mcp
../.venv/bin/python -m pytest \
  tests/unit/core/test_run_registry_architecture.py \
  tests/unit/core/test_run_registry_lifecycle.py \
  tests/unit/core/test_run_registry_metadata.py \
  tests/unit/core/test_run_registry_events.py \
  tests/unit/core/test_run_repository_transactions.py \
  tests/unit/core/test_operation_repository.py \
  tests/unit/core/test_artifact_repository_transactions.py \
  tests/unit/core/test_run_registry_compatibility.py \
  tests/unit/test_runs.py \
  tests/unit/test_lineage_ledger.py \
  tests/unit/http/services/test_operation_service.py \
  tests/unit/test_http_routes.py \
  tests/unit/tools/test_train.py \
  tests/unit/tools/test_run_management.py \
  tests/unit/tools/test_run_compare.py \
  tests/chaos/test_registry_concurrency.py -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Run strict static checks over all affected modules**

```bash
cd fovux-mcp
../.venv/bin/ruff check src/fovux/core/runs.py src/fovux/core/run_registry tests/unit/core
../.venv/bin/ruff format --check src/fovux/core/runs.py src/fovux/core/run_registry tests/unit/core
../.venv/bin/mypy src/fovux/core/runs.py src/fovux/core/run_registry --strict
```

Expected: no errors.

- [ ] **Step 8: Commit the compatibility cutover**

```bash
git add fovux-mcp/src/fovux/core/runs.py fovux-mcp/src/fovux/core/run_registry fovux-mcp/tests/unit/core/test_run_registry_compatibility.py
git commit -m "refactor(registry): compose compatibility facade"
```

---

### Task 7: Full Verification, Documentation Truth, and Pull Request

**Files:**
- Modify if required by truth checks: `docs/architecture.md`
- Modify if required by test strategy: `fovux-mcp/docs/testing-and-coverage.md`
- Modify: `docs/superpowers/plans/2026-07-23-run-registry-boundaries.md` checkboxes

**Interfaces:**
- Consumes: completed facade and repositories.
- Produces: a reviewable PR that closes #175 and contains current bot/agent evidence.

- [ ] **Step 1: Run complete Python quality suite**

```bash
cd fovux-mcp
../.venv/bin/ruff check src tests
../.venv/bin/ruff format --check src tests
../.venv/bin/mypy src/fovux --strict
../.venv/bin/python -m pytest --cov=src/fovux --cov-report=term-missing --cov-report=xml -q
```

Expected: Ruff/mypy clean; complete test suite passes; backend coverage remains at or above 85%.

- [ ] **Step 2: Run Studio and packaged-contract regression checks**

```bash
cd fovux-studio
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test
corepack pnpm build
```

Expected: lint/typecheck/tests/build pass without public message-contract changes.

- [ ] **Step 3: Run repository policy and workflow checks**

From repository root:

```bash
python scripts/check_test_strategy.py
python scripts/check_docs_truth.py
python scripts/check_api_stability_plan.py
python scripts/check_release_truth.py
python scripts/check_tool_contracts.py
python scripts/check_studio_lm_tools.py
python scripts/check_agent_policy.py
actionlint -shellcheck= -pyflakes=
```

Expected: all scripts and actionlint exit zero. If the repository-standard actionlint path differs, use the pinned version from CI without modifying workflow pins.

- [ ] **Step 4: Inspect the final diff for boundary and compatibility drift**

Run:

```bash
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
git grep -n "from fovux.core.runs" -- fovux-mcp/src fovux-mcp/tests
git grep -n "fovux.core.runs\|run_registry.facade" -- fovux-mcp/src/fovux/core/run_registry
```

Expected: the first grep confirms callers remain compatible; the second returns matches only in the architecture test's forbidden-import literals, not production lower-level modules.

- [ ] **Step 5: Push and open the PR**

```bash
git push --set-upstream origin fix/175-run-registry-boundaries
```

Open a non-draft PR titled `refactor(registry): split lifecycle, events, and persistence boundaries` with:

```markdown
Closes #175

## Summary
- keep `fovux.core.runs` and `RunRegistry` fully compatible
- separate schema/database, lifecycle, event, run, operation, artifact, and catalog ownership
- make run transitions and event/audit writes explicitly transactional
- preserve SQLite schema and existing database migration behavior

## Verification
- full backend test and coverage suite
- strict mypy, Ruff, Studio lint/typecheck/test/build
- architecture/import-direction and rollback tests
- repository policy and workflow validation
```

- [ ] **Step 6: Review all bot and agent feedback before merge**

Inspect:

```bash
gh pr checks <PR_NUMBER> --repo oaslananka/fovux-kit
gh pr view <PR_NUMBER> --repo oaslananka/fovux-kit --json comments,reviews,reviewDecision,mergeable,mergeStateStatus

gh api repos/oaslananka/fovux-kit/pulls/<PR_NUMBER>/comments
```

Read and resolve Sonar, Codecov, CodeQL, Semgrep, DeepScan, security, review-thread, and any agent comments. Do not merge while a relevant finding, unresolved thread, required check, or compatibility concern remains.

- [ ] **Step 7: Squash merge and verify main**

Merge only when the PR is `CLEAN/MERGEABLE`, every required check is green, Sonar has zero unresolved issue/hotspot, and bot/agent feedback has been evaluated. Then verify the merge commit's `main` CI, CodeQL, security, release, and Studio VSIX workflows.
