# HTTP Service Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the cyclic 1,500-line HTTP route module with domain route adapters and independently testable services while preserving every existing local API and security behavior.

**Architecture:** `app.py` composes an injected `HttpServices` container and a domain router package. Route modules depend on services; services depend on core registries, challenge primitives, and tool policy/invocation functions; neither routes nor services imports `app.py`. Thread-local output capture moves into a dedicated leaf module.

**Tech Stack:** Python 3.12+, FastAPI/Starlette, asyncio, SQLAlchemy-backed `RunRegistry`, pytest, Ruff, mypy.

## Global Constraints

- Preserve all endpoint paths, HTTP methods, status codes, response bodies, SSE formats, and headers.
- Preserve authentication, session scopes, origin checks, body limits, rate limits, challenges, path policy, audit fields, timeouts, concurrency limits, and operation persistence.
- Do not change the public MCP tool contract or add a remote/public transport.
- Route files: at most 260 lines; route handlers: at most 60 lines.
- Service files: at most 520 lines; public service methods: at most 110 lines.
- No route or service module may import `fovux.http.app`.

---

### Task 1: Architecture Guards and Thread Stream Boundary

**Files:**
- Create: `fovux-mcp/tests/unit/test_http_service_architecture.py`
- Create: `fovux-mcp/src/fovux/http/thread_stream.py`
- Modify: `fovux-mcp/src/fovux/http/app.py`

**Interfaces:**
- Produces: `install_thread_local_streams() -> None`
- Produces: `redirect_thread_output(stream: TextIO) -> ContextManager[None]`
- Enforces: no `fovux.http.app` imports below routes/services and source budgets.

- [ ] **Step 1: Write failing architecture and thread-redirection tests**

Add tests that scan `src/fovux/http/routes/**/*.py` and `src/fovux/http/services/**/*.py` for imports
from `fovux.http.app`, enforce the global budgets, and verify a `StringIO` receives output only inside
`redirect_thread_output()`.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTHONPATH=src python -m pytest -q tests/unit/test_http_service_architecture.py
```

Expected: FAIL because `thread_stream.py`, route package, and service package do not exist and the
current monolithic route file exceeds the budget.

- [ ] **Step 3: Move thread-local stream infrastructure**

Implement `ThreadLocalStream`, `_THREAD_LOCAL`, `install_thread_local_streams()`, and
`redirect_thread_output()` in `thread_stream.py`. Replace the definitions in `app.py` with an import
and one `install_thread_local_streams()` call. Do not change fallback writes or flush behavior.

- [ ] **Step 4: Run focused stream and HTTP baseline tests**

```bash
PYTHONPATH=src python -m pytest -q \
  tests/unit/test_http_service_architecture.py::test_thread_output_redirect_is_scoped \
  tests/security/test_http_security.py::test_health_endpoint_does_not_require_auth
```

Expected: PASS for thread redirection; architecture budget tests remain RED until later tasks.

- [ ] **Step 5: Commit**

```bash
git add fovux-mcp/src/fovux/http/thread_stream.py fovux-mcp/src/fovux/http/app.py \
  fovux-mcp/tests/unit/test_http_service_architecture.py
git commit -m "refactor(http): isolate thread-local output capture"
```

### Task 2: Service Container and Run Domain

**Files:**
- Create: `fovux-mcp/src/fovux/http/services/__init__.py`
- Create: `fovux-mcp/src/fovux/http/services/container.py`
- Create: `fovux-mcp/src/fovux/http/services/errors.py`
- Create: `fovux-mcp/src/fovux/http/services/runs.py`
- Create: `fovux-mcp/src/fovux/http/routes/runs.py`
- Create: `fovux-mcp/tests/unit/http/services/test_run_service.py`

**Interfaces:**
- Produces: `ServiceError(status_code: int, detail: object)`
- Produces: `RunService.list_runs()`, `get_run(run_id)`, `search_runs(filters)`,
  `resolve_run_dir(run_id)`, `metric_event_stream(...)`, and metric helper methods.
- Produces: `HttpServices.runs: RunService`.

- [ ] **Step 1: Write service-level tests with a fake registry**

Cover status-file precedence, malformed tag JSON fallback, query/status/tag/min-mAP filtering, missing
run errors, initial metric snapshots, appended metric deltas, and terminal SSE completion without a
FastAPI client.

- [ ] **Step 2: Verify RED**

```bash
PYTHONPATH=src python -m pytest -q tests/unit/http/services/test_run_service.py
```

Expected: import failure because `RunService` does not exist.

- [ ] **Step 3: Implement RunService and typed ServiceError**

Move run serialization and metric-stream orchestration from the monolith. Inject a registry provider
and checkpoint readers with production defaults. Keep JSON field names and stream strings byte-for-byte
compatible.

- [ ] **Step 4: Add thin run routes**

Each handler obtains `request.app.state.http_services.runs`, calls one service method, and maps
`ServiceError` to `HTTPException`. Streaming handlers only create `StreamingResponse` with the existing
headers.

- [ ] **Step 5: Verify service and existing run tests**

```bash
PYTHONPATH=src python -m pytest -q \
  tests/unit/http/services/test_run_service.py \
  tests/unit/test_http_routes.py -k 'run or metric or stream or search'
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add fovux-mcp/src/fovux/http/services fovux-mcp/src/fovux/http/routes/runs.py \
  fovux-mcp/tests/unit/http/services/test_run_service.py
git commit -m "refactor(http): extract run service"
```

### Task 3: Challenge and Tool Invocation Services

**Files:**
- Create: `fovux-mcp/src/fovux/http/services/tools.py`
- Create: `fovux-mcp/src/fovux/http/routes/tools.py`
- Create: `fovux-mcp/tests/unit/http/services/test_tool_services.py`

**Interfaces:**
- Produces: `ToolRuntimeState` containing challenge, semaphore, running-operation, and completed-result maps.
- Produces: `ChallengeService.request(tool_name, payload) -> ChallengeOutcome`.
- Produces: `ToolInvocationService.invoke(context, tool_name, payload) -> ToolOutcome`.
- Consumes: existing `policy_for_tool`, `payload_hash`, `invoke_tool`, challenge verification, and audit logger.

- [ ] **Step 1: Write failing service tests**

Cover read-only challenge rejection, risky challenge creation/effect summary, exact argument binding,
completed timeout-result replay, in-flight operation 202 outcome, semaphore rejection, validation/domain
error mapping, successful invocation, and audit metadata.

- [ ] **Step 2: Verify RED**

```bash
PYTHONPATH=src python -m pytest -q tests/unit/http/services/test_tool_services.py
```

Expected: import failure because the services do not exist.

- [ ] **Step 3: Implement service state and outcomes**

Move helper functions and the 240-line invocation orchestration into focused service methods and
private helpers. Service code must not import FastAPI or Starlette. Preserve operation IDs, result TTL,
maximum retained results, timeout continuation, deferred semaphore release, and audit field values.

- [ ] **Step 4: Implement thin tool routes**

Map `ChallengeOutcome` and `ToolOutcome` to the existing response codes/content. Convert typed service
errors to the exact existing `HTTPException` details.

- [ ] **Step 5: Verify all challenge/tool tests**

```bash
PYTHONPATH=src python -m pytest -q \
  tests/unit/http/services/test_tool_services.py \
  tests/unit/test_http_challenge.py \
  tests/unit/test_http_policy_modes.py \
  tests/unit/test_http_routes.py -k 'tool or challenge or semaphore or timeout or operation_result'
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add fovux-mcp/src/fovux/http/services/tools.py fovux-mcp/src/fovux/http/routes/tools.py \
  fovux-mcp/tests/unit/http/services/test_tool_services.py
git commit -m "refactor(http): extract tool services"
```

### Task 4: Persistent Operation Service

**Files:**
- Create: `fovux-mcp/src/fovux/http/services/operations.py`
- Create: `fovux-mcp/src/fovux/http/routes/operations.py`
- Create: `fovux-mcp/tests/unit/http/services/test_operation_service.py`

**Interfaces:**
- Produces: `OperationRuntimeState(active_tasks, sse_listeners)`.
- Produces: `OperationService.create`, `get`, `cancel`, `result`, `log_stream`, `event_stream`, and
  `run_in_background`.
- Consumes: registry provider, tool policy/scope/check/invoker dependencies, `redirect_thread_output`.

- [ ] **Step 1: Write failing service tests**

Use a fake registry and invoker to cover idempotent create, pending-to-running-to-success persistence,
result persistence, failure persistence, cancellation, listener notification, event replay, and scoped
operation-log output without `TestClient`.

- [ ] **Step 2: Verify RED**

```bash
PYTHONPATH=src python -m pytest -q tests/unit/http/services/test_operation_service.py
```

Expected: import failure because `OperationService` does not exist.

- [ ] **Step 3: Implement OperationService**

Move background operation logic and serializers. Inject registry/invoker/train-stop dependencies. Use
`redirect_thread_output()` instead of importing application thread state. Keep registry event ordering,
status values, log file locations, cancellation behavior, and listener payloads unchanged.

- [ ] **Step 4: Add operation routes**

Keep request parsing and auth-scope extraction in the route adapter. Delegate policy/challenge checks
and orchestration to the service. Keep existing response codes and SSE headers.

- [ ] **Step 5: Verify operation routes and services**

```bash
PYTHONPATH=src python -m pytest -q \
  tests/unit/http/services/test_operation_service.py \
  tests/unit/test_http_routes.py -k 'operation or events or logs or cancel'
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add fovux-mcp/src/fovux/http/services/operations.py \
  fovux-mcp/src/fovux/http/routes/operations.py \
  fovux-mcp/tests/unit/http/services/test_operation_service.py
git commit -m "refactor(http): extract operation service"
```

### Task 5: Lineage, Dataset, Export, and Health Domains

**Files:**
- Create: `fovux-mcp/src/fovux/http/services/lineage.py`
- Create: `fovux-mcp/src/fovux/http/services/health.py`
- Create: `fovux-mcp/src/fovux/http/routes/lineage.py`
- Create: `fovux-mcp/src/fovux/http/routes/resources.py`
- Create: `fovux-mcp/src/fovux/http/routes/health.py`
- Create: `fovux-mcp/tests/unit/http/services/test_lineage_service.py`
- Create: `fovux-mcp/tests/unit/http/services/test_health_service.py`

**Interfaces:**
- Produces: `LineageService.run_lineage`, `run_events`, `list_datasets`, `get_dataset`, `list_exports`.
- Produces: `HealthService.health()` and `prometheus_metrics(enabled)`.

- [ ] **Step 1: Write failing service tests**

Cover missing records, JSON decoding fallbacks, artifact/export/event serialization, dataset lookup,
export listing, health version payload, disabled metrics, and active/total run metrics.

- [ ] **Step 2: Verify RED**

```bash
PYTHONPATH=src python -m pytest -q \
  tests/unit/http/services/test_lineage_service.py \
  tests/unit/http/services/test_health_service.py
```

Expected: import failure.

- [ ] **Step 3: Implement services and thin routes**

Move serialization unchanged. `HealthService` raises a typed not-enabled error; route mapping retains
404. `LineageService` uses an injected registry provider and returns plain mappings/lists.

- [ ] **Step 4: Verify lineage, resource, and health coverage**

```bash
PYTHONPATH=src python -m pytest -q \
  tests/unit/http/services/test_lineage_service.py \
  tests/unit/http/services/test_health_service.py \
  tests/unit/test_lineage_ledger.py \
  tests/unit/test_shutdown.py \
  tests/unit/test_http_routes.py -k 'health or metrics or dataset or export'
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add fovux-mcp/src/fovux/http/services/lineage.py \
  fovux-mcp/src/fovux/http/services/health.py \
  fovux-mcp/src/fovux/http/routes/lineage.py \
  fovux-mcp/src/fovux/http/routes/resources.py \
  fovux-mcp/src/fovux/http/routes/health.py \
  fovux-mcp/tests/unit/http/services/test_lineage_service.py \
  fovux-mcp/tests/unit/http/services/test_health_service.py
git commit -m "refactor(http): extract lineage and health services"
```

### Task 6: Router Aggregation, App Injection, and Monolith Removal

**Files:**
- Create: `fovux-mcp/src/fovux/http/routes/__init__.py`
- Modify: `fovux-mcp/src/fovux/http/services/container.py`
- Modify: `fovux-mcp/src/fovux/http/app.py`
- Delete: `fovux-mcp/src/fovux/http/routes.py`
- Modify: `fovux-mcp/tests/unit/test_http_routes.py`
- Modify: `fovux-mcp/tests/unit/test_http_service_architecture.py`

**Interfaces:**
- Produces: `build_http_router() -> APIRouter`.
- Produces: `build_default_services() -> HttpServices`.
- Changes: `create_app(*, enable_metrics=False, services: HttpServices | None=None) -> FastAPI`.

- [ ] **Step 1: Add failing composition tests**

Assert injected fake services are stored on app state, all historical OpenAPI paths/methods remain,
route names are unique, and importing every route/service module never imports `fovux.http.app`.

- [ ] **Step 2: Verify RED**

```bash
PYTHONPATH=src python -m pytest -q \
  tests/unit/test_http_service_architecture.py \
  tests/contract/test_api_schema.py
```

Expected: FAIL while the monolith and old composition remain.

- [ ] **Step 3: Assemble routers and service container**

Include all domain routers once. Store the container and compatibility state aliases on `app.state`.
Keep middleware order, lifespan, CORS, rate limiter, and non-local bind behavior unchanged.

- [ ] **Step 4: Remove monolith and preserve internal helper exports**

Delete `routes.py`. Re-export metric and timed-tool helpers from `routes/__init__.py` so existing internal
unit imports continue to resolve while patch targets are updated to their owning service modules.

- [ ] **Step 5: Run architecture, OpenAPI, HTTP, security, and integration tests**

```bash
PYTHONPATH=src python -m pytest -q \
  tests/unit/test_http_service_architecture.py \
  tests/unit/test_http_routes.py \
  tests/unit/test_http_challenge.py \
  tests/unit/test_http_policy_modes.py \
  tests/unit/test_lineage_ledger.py \
  tests/unit/test_shutdown.py \
  tests/security/test_http_security.py \
  tests/contract/test_api_schema.py \
  tests/integration/test_real_server_smoke.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A fovux-mcp/src/fovux/http fovux-mcp/tests/unit/test_http_routes.py \
  fovux-mcp/tests/unit/test_http_service_architecture.py
git commit -m "refactor(http): compose domain routers and services"
```

### Task 7: ADR, Documentation, and Final Verification

**Files:**
- Create: `fovux-mcp/docs/adr/0010-http-service-boundary.md`
- Modify: `docs/architecture.md`
- Modify: `docs/testing-strategy.md` if the existing service-test policy needs an explicit entry.

**Interfaces:**
- Documents: one-way dependency direction, injection boundary, compatibility guarantees, and extension points.

- [ ] **Step 1: Write ADR and architecture documentation**

Record context, decision, route/service ownership, thread-stream extraction, error mapping,
consequences, and validation commands. Link the ADR from the architecture document.

- [ ] **Step 2: Run formatting and strict type checks**

```bash
PYTHONPATH=src python -m ruff check src/fovux/http tests/unit/http tests/unit/test_http_service_architecture.py
PYTHONPATH=src python -m ruff format --check src/fovux/http tests/unit/http tests/unit/test_http_service_architecture.py
PYTHONPATH=src python -m mypy --strict src/fovux/http
```

Expected: zero findings.

- [ ] **Step 3: Run all repository verification gates**

```bash
PYTHONPATH=src python -m pytest -q --ignore=tests/contract/test_mcp_protocol.py
PYTHONPATH=src python ../scripts/check_tool_contracts.py
PYTHONPATH=src python ../scripts/check_docs_truth.py
PYTHONPATH=src python ../scripts/check_task_docs.py
PYTHONPATH=src python ../scripts/check_test_strategy.py
git diff --check
```

Expected: all commands exit 0. If the raw stdio contract is run on a clean GitHub runner, it must pass
there before merge.

- [ ] **Step 4: Verify acceptance criteria explicitly**

Confirm the architecture test reports no cycle, all route/service budgets pass, service tests use no
`TestClient`, OpenAPI is unchanged, HTTP/security tests pass, and the ADR exists.

- [ ] **Step 5: Commit**

```bash
git add fovux-mcp/docs/adr/0010-http-service-boundary.md docs/architecture.md \
  docs/testing-strategy.md
git commit -m "docs(http): document service boundary"
```

- [ ] **Step 6: Push, open PR, inspect every bot/agent review, fix findings, and merge**

Use head-SHA matching for merge. Required checks are `ci-required`, `security-required`,
`dependency-review`, and `codeql-required`. Inspect issue comments, PR reviews, review comments,
check-run summaries, Codecov, SonarQube Cloud, Socket, DeepScan, Semgrep, Trivy, OSV, and CodeQL before
merging.
