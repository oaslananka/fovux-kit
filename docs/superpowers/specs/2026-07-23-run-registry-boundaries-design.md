# Run Registry Boundary Decomposition Design

**Date:** 2026-07-23

**Issue:** #175
**Status:** Approved through the issue acceptance criteria and maintainer instruction to continue implementation

## 1. Purpose

`fovux-mcp/src/fovux/core/runs.py` combines ORM declarations, SQLite engine setup,
schema migration, run lifecycle rules, operation persistence, durable event history,
lineage metadata, artifact hashing, query methods, and process-local registry caching in
one 1,176-line module. The decomposition must reduce review and change risk without
changing the public `fovux.core.runs` API, SQLite schema, MCP tools, HTTP contracts, or
persisted record semantics.

## 2. Constraints

- Existing imports from `fovux.core.runs` continue to work.
- Existing ORM table and column names remain unchanged.
- Existing databases migrate in place; no destructive or data-copy migration is introduced.
- Run and operation lifecycle writes remain synchronous SQLite transactions.
- SQLite remains the only registry backend.
- HTTP and MCP callers continue to use `RunRegistry` and the existing method names.
- Filesystem inspection and hashing happen before opening write transactions.
- No remote database, event broker, ORM replacement, or public contract version is added.

## 3. Approaches Considered

### 3.1 File extraction only

Move classes and methods into separate files but keep one large inheritance chain or a set
of mixins. This minimizes forwarding code, but responsibility ownership remains implicit,
transaction boundaries are still spread across mixins, and lower-level modules can call
one another through a partially initialized facade.

### 3.2 Replace the public registry with repositories

Expose new repositories directly to HTTP, tools, and tests. This creates clean boundaries,
but changes dozens of imports and makes a behavior-preserving refactor unnecessarily risky.
It also violates the compatibility requirement unless accompanied by a migration period.

### 3.3 Compatibility facade with composed repositories — selected

Keep `RunRegistry` as the public facade and delegate to focused components that share one
session factory. The facade preserves method signatures and ORM return types. Lower-level
components own lifecycle, event, query, and filesystem responsibilities explicitly, while
`fovux.core.runs` becomes a stable re-export and singleton-cache module.

This approach provides reviewable boundaries now and permits callers to adopt narrower
interfaces later without requiring that migration in #175.

## 4. Module Boundaries

The new package is `fovux.core.run_registry`.

### 4.1 `models.py`

Owns SQLAlchemy `Base`, `UtcDateTime`, datetime serialization helpers, and every existing
ORM record class. It has no dependency on repositories, lifecycle policy, or the facade.
Table names, columns, defaults, indexes, and serialized field formats remain unchanged.

### 4.2 `database.py`

Owns engine creation, SQLite pragmas, session-factory creation, schema creation, and
migration execution. It depends only on SQLAlchemy and `models.py`. The database object
exposes a session factory and `close()`; repositories never create engines themselves.

### 4.3 `lifecycle.py`

Owns `RunStatus`, `OperationStatus`, terminal-state definitions, valid transition maps,
and timestamp mutation rules. Repositories must call these policies before assigning a
status. Invalid transitions raise `ValueError` with the existing run error wording and a
parallel operation error wording. Repeating the current status remains a no-op transition
that can still apply explicitly supplied metadata such as a PID or operation result.

### 4.4 `metadata.py`

Owns run metadata computation and filesystem-facing lineage preparation: dataset
fingerprinting, configuration hashing, version/environment summaries, dataset class-map
loading, and artifact digest/size inspection. Expensive or failure-prone filesystem work
finishes before a database write transaction starts. Expected fallback behavior remains
the same as the monolith.

### 4.5 `events.py`

Owns durable run-event, operation-event, and audit-event writes and reads. Event append
helpers accept an existing SQLAlchemy `Session` when the event must participate in a
larger transaction. Public standalone event methods open and commit their own transaction.
Operation-event IDs remain the durable ordering key and are queried in ascending order for
SSE resume.

### 4.6 `run_repository.py`

Owns run creation, atomic concurrency reservation, lookup, filtering, tag/extra updates,
deletion, and run status transitions. It coordinates metadata preparation and event-store
helpers but does not own engine setup or ORM declarations.

### 4.7 `operation_repository.py`

Owns operation creation, idempotency lookup, status/progress mutation, and operation
queries. All status assignments pass through `OperationLifecyclePolicy`. Durable HTTP/SSE
operation events remain explicit event-store writes so the operation service can persist
one canonical event and fan out that exact event ID, preserving #171 semantics.

### 4.8 `artifact_repository.py`

Owns artifact registration, export registration, artifact hashing, and artifact/export
queries. `record_export` writes the export and its associated artifact in one transaction;
file metadata is computed before that transaction.

### 4.9 `catalog_repository.py`

Owns dataset/model lineage registration, dataset queries, metrics, and active-learning
review queue persistence. Run creation calls a session-aware lineage registration method
inside the same transaction as the run row and initial pending event.

### 4.10 `facade.py`

Constructs the database and repositories, then exposes the existing `RunRegistry` methods
as explicit forwarding methods. It does not duplicate SQL, state machines, event creation,
or filesystem logic. Component attributes are private implementation details.

### 4.11 `fovux.core.runs`

Remains the compatibility module. It re-exports all existing ORM classes, status types,
`RunRegistry`, and datetime helpers needed by existing callers. It continues to own the
process-local `get_registry`/`close_registry` cache and lock so singleton behavior is
unchanged.

## 5. Dependency Direction

Dependencies flow in one direction:

```text
fovux.core.runs
    -> run_registry.facade
        -> run_repository / operation_repository / artifact_repository / catalog_repository
            -> lifecycle / metadata / events
                -> database / models
```

`models.py`, `database.py`, `lifecycle.py`, `metadata.py`, and `events.py` must not import
`RunRegistry`, `run_registry.facade`, or `fovux.core.runs`. Repository modules must not
import the compatibility module. An architecture test parses imports to enforce this rule.

## 6. Transaction and Event Semantics

- `create_run` and `reserve_run_slot`: metadata is computed first; one transaction writes
  the run, dataset/model lineage rows, and initial `pending` run event.
- `update_status`: one transaction validates the transition, updates timestamps/PID, and
  writes the run transition event plus audit event.
- `create_operation`, operation status/progress updates, and operation-event appends each
  retain explicit transactions. The HTTP operation service remains responsible for the
  exact event payload and live fan-out established in #171.
- `add_artifact`: digest/size inspection occurs first; one transaction merges the artifact
  and writes its audit event.
- `record_export`: digest/size inspection occurs first; one transaction writes the export,
  associated artifact, and artifact audit event.
- Read methods use short-lived sessions and return detached ORM records exactly as today.
- Operation events are ordered by autoincrement ID; run/audit/artifact query ordering stays
  unchanged.

## 7. Compatibility

The following remain stable:

- imports such as `from fovux.core.runs import RunRegistry, RunRecord`;
- every existing `RunRegistry` method name, argument order, default, and returned ORM type;
- the process-local registry singleton cache;
- SQLite file location, tables, columns, indexes, migration version, and JSON encodings;
- missing-record behavior (`None`, `False`, or no-op according to the current method);
- run lifecycle error type and message prefix;
- HTTP operation exactly-once event persistence and SSE replay behavior.

New internal classes are not declared public API in this change.

## 8. Error Handling

- Filesystem metadata keeps the current best-effort fallbacks.
- Invalid run or operation transitions fail before any row or event is committed.
- A failure while appending a run transition event or audit record rolls back the status
  mutation because all three writes share one transaction.
- A failure while registering an export artifact rolls back the export row.
- SQLite and SQLAlchemy exceptions propagate unchanged; the facade does not translate them.

## 9. Testing

Focused tests will cover:

- compatibility re-exports and singleton cache behavior;
- import-direction constraints;
- run and operation transition policies independently of HTTP;
- rollback of run state when transactional event persistence fails;
- operation-event ordering and resume filtering;
- atomic export/artifact persistence;
- migration of a pre-v1 SQLite database while preserving an existing row;
- repository boundaries with direct unit tests;
- existing run, lineage, operation-service, HTTP, tool, migration, Studio, and chaos suites.

The final verification includes Ruff, formatting, strict mypy, the complete Python test
suite with coverage, Studio lint/typecheck/test/build, actionlint, and repository policy
checks used by the required CI lane.

## 10. Delivery Strategy

The work is delivered as one compatibility-preserving pull request with small commits:

1. architecture contract, models, and database boundary;
2. lifecycle and event-store boundaries;
3. run and operation repositories;
4. artifact and catalog repositories;
5. facade and compatibility module cutover;
6. ADR, focused transaction tests, and full regression verification.

At each commit, existing callers continue importing `fovux.core.runs`; no intermediate
commit intentionally changes the public contract.
