# ADR 0011 — Run Registry Responsibility Boundaries

## Status

Accepted on 23 July 2026.

## Context

`fovux.core.runs` grew to include SQLAlchemy models, SQLite setup and migrations,
run and operation lifecycle mutation, event history, lineage metadata, artifact
hashing, read queries, and process-local caching. The public module is widely
imported by tools, HTTP services, tests, and workers, so replacing it directly
would create unnecessary compatibility risk.

## Decision

Keep `fovux.core.runs` as the stable compatibility module and keep `RunRegistry`
as the public facade. Move implementation into the composed
`fovux.core.run_registry` package with these owners:

- `models.py`: ORM schema and datetime serialization;
- `database.py`: engine, SQLite pragmas, sessions, and migrations;
- `lifecycle.py`: run and operation transition policy and timestamps;
- `metadata.py`: filesystem-derived run and artifact metadata;
- `events.py`: durable run, operation, and audit event storage;
- `run_repository.py`: run commands and queries;
- `operation_repository.py`: operation commands and queries;
- `artifact_repository.py`: artifacts and exports;
- `catalog_repository.py`: datasets, models, metrics, and review queue;
- `facade.py`: explicit compatibility delegation.

Dependencies flow from the compatibility facade toward repositories and then
toward policy, metadata, database, and models. Lower-level modules never import
the facade or `fovux.core.runs`.

Run creation, lineage registration, and the initial run event share one
transaction. Run status, transition event, and audit event share one
transaction. Filesystem hashing occurs before write transactions. Operation
status persistence and HTTP/SSE operation-event persistence remain explicit
separate transactions so the HTTP service can fan out the exact persisted event
ID established by the exactly-once event contract.

## Compatibility

Existing `fovux.core.runs` imports, `RunRegistry` method signatures, ORM table and
column names, JSON formats, migration version, SQLite location, and singleton
cache behavior remain stable. SQLite remains the registry backend.

## Consequences

- Lifecycle rules and transaction ownership can be tested without HTTP.
- Schema changes and filesystem work no longer share a review surface with every
  query method.
- The facade contains forwarding code, but that duplication is intentionally
  shallow and protects public callers.
- Future callers may adopt narrower repository interfaces, but that migration is
  outside this decision.
