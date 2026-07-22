# Testing and Code Coverage Policy

This document outlines the testing strategies, pipeline configurations, and code coverage rules
used in Fovux MCP.

## 1. Test Execution Pipelines

To balance rapid feedback loops during PR reviews with thorough correctness guarantees, Fovux
separates verification into two main pipelines:

### Fast PR Checks
- **Scope:** Linting (`ruff`), strict type checking (`mypy`), and unit tests.
- **Trigger:** Runs automatically on every pull request and push.
- **Command:** `pnpm check` (Studio) and `task test:fast` (MCP server backend).
- **Execution:** Runs only unit tests that do not require external network access, physical GPUs,
  or long-running training loops (`not slow and not integration and not gpu`).

### Nightly / Scheduled Checks
- **Scope:** Exhaustive integration testing, mutation testing, and performance benchmark tracking.
- **Trigger:** Runs on a nightly cron job or scheduled execution.
- **Command:** `task test:cov` (full coverage) and `task ci`.
- **Execution:** Executes end-to-end training runs (with `FOVUX_RUN_SLOW_TESTS=1` enabled), full
  ONNX/TFLite export pipelines, live RTSP stream mocks, and mutation tests (`mutmut`).

---


## 2. Golden Dataset Contract

Golden dataset edge cases are generated deterministically in
`tests/unit/tools/test_golden_dataset.py`. The fixture creates a compact YOLO-style dataset with:

- Unicode folder and file names;
- corrupt and empty image cases;
- missing labels;
- class-count and class-id mismatches;
- duplicate/leakage cases across train and validation splits;
- Windows-style path separators inside `data.yaml`.

This keeps the corpus reproducible without committing large binary assets. Any new dataset-quality
rule must either extend this fixture or add another deterministic fixture under `tests/fixtures/`.

## 3. Runtime and Export Contract Coverage

Runtime-heavy paths are covered with contract or mocked integration tests so fast PR checks remain
usable while still protecting behavior:

| Area | Primary coverage | Strategy |
| :--- | :--- | :--- |
| Training worker | `tests/unit/test_train_worker.py`, `tests/integration/test_pipeline_integration.py` | Mocked worker launch/status plus module-entry coverage. |
| ONNX/TFLite export | `tests/unit/tools/test_export.py`, `tests/integration/test_pipeline_integration.py` | Mocked Ultralytics export and parity checks. |
| Image/batch inference | `tests/unit/tools/test_diagnostics_tools.py`, `tests/unit/tools/test_inference_management.py` | Mocked model predictions and serialized-output assertions. |
| RTSP inference | `tests/unit/tools/test_inference_management.py`, `tests/integration/test_pipeline_integration.py` | Fake capture/writer objects, reconnect loops, and frame-processing counters. |
| Dataset benchmarks | `tests/bench/test_dataset_benchmarks.py` | `pytest-benchmark` baselines for inspection and duplicate detection. |

## Coverage Signals and Merge Authority

The merge-blocking authority is the required `ci-required` aggregate. Its quality lane enforces
**85% backend line coverage** and a **45% Studio line-coverage floor**, then validates both
artifacts with `scripts/check_coverage_reports.py` before any external upload. Missing, empty,
below-threshold, or cross-routed reports fail the required lane. Studio LCOV is source-only;
`test/**` helpers are excluded before report generation.

Coverage is generated and routed as follows:

| Surface | Required report | Required threshold | External routing |
| :--- | :--- | :--- | :--- |
| Python backend | `fovux-mcp/coverage.xml` | 85% lines | Codecov flag/component `backend`; Sonar Python coverage |
| Fovux Studio | `fovux-studio/coverage/lcov.info` | 45% lines | Codecov flag/component `studio`; Sonar JavaScript/TypeScript coverage |

SonarQube Cloud Automatic Analysis was disabled on **2026-07-22** because that mode does not ingest
external coverage reports or repository scanner properties. The required quality lane now runs the
SHA-pinned Sonar scanner after report validation and waits up to 300 seconds for the Sonar quality
gate. For pull requests, Sonar's new-code baseline is the target branch and the scanner consumes the
same backend XML and Studio LCOV artifacts produced by the required lane.

Codecov uploads remain OIDC-based. The combined project status uses an explicit **80% target** and
the patch status uses an **85% target**; both allow **1% tolerance** and are non-informational, so
their GitHub pass/fail state matches the thresholds shown in the Codecov comment. Codecov waits for
exactly two coverage uploads (`backend` and `studio`), does not wait for unrelated CI providers,
and uses an explicit final `send-notifications` step after all coverage and test-result uploads. The
manual trigger produces one finalized status/comment set and surfaces processing errors. This keeps
the external signal prompt and observable without making it the repository's merge authority.

Backend and Studio remain separate through non-carryforward flags and named components. The
documented backend omit list is mirrored in Codecov `ignore` and Sonar coverage exclusions so both
services evaluate the same source scope. Component floors remain informational at **85% for the
backend** and **45% for Studio**. The Studio floor is a truthful ratchet baseline above which
coverage must remain while new-code patch coverage stays at 85%; it must only move upward as
coverage improves. Codecov supplies detailed diff diagnostics; `ci-required` remains the branch-rule
merge authority so an external service delay cannot redefine the repository's deterministic coverage
gate.

Sonar can display `0.0% Coverage on New Code` when `new_lines_to_cover` is zero. In that case the
value means the pull request introduced no coverable production lines; it is not evidence that the
Cobertura or LCOV reports were missing. Report-ingestion health is instead confirmed by non-zero
project coverage/line counts and by the required pre-upload validator.

## 4. Code Coverage Omit List & Rationales

To maintain a meaningful coverage gate (minimum 85% required on included files), we exclude
certain entry points and integration-heavy adapters where line-by-line coverage checks produce
brittle or low-value tests. Below is the list of omitted paths and their rationales:

| Excluded File/Pattern | Rationale | How It Is Verified |
| :--- | :--- | :--- |
| `**/__main__.py` | CLI/Module entry point. Contains only bootstrap boilerplate. | Covered via CLI command execution smoke tests. |
| `**/cli.py` | Typer command-line interface logic. Primarily configuration and parsing. | Verified via end-to-end subprocess tests in the test suite. |
| `**/core/dataset_utils.py` | Filesystem and dataset-discovery helper paths are better validated through tool-level fixtures. | Covered by dataset inspect/validate/convert/split tests and golden dataset fixtures. |
| `**/core/train_worker.py` | Detached backend worker process logic designed to run in a separate process. | Tested via mock subprocess spawning tests and E2E training logs. |
| `**/core/ultralytics_adapter.py` | Third-party Ultralytics library adapter wrapper. | Checked indirectly via training, eval, and inference tool suites. |
| `**/tools/export_tflite.py` | Integration with external TensorFlow/Keras libraries for compilation. | Covered by mock integration tests verifying correct exported file paths. |
| `**/tools/deployment_advise.py` | Target advice is rule-table oriented and hardware-dependent. | Covered by focused deployment advice unit tests and release docs truth checks. |
| `**/tools/demo_init.py` | Demo scaffold generation is template-heavy and validated through command/output contracts. | Covered by demo/tool documentation checks and planned Studio onboarding smoke tests. |
| `**/tools/infer_image.py` | YOLO prediction pipeline that interacts with model weights. | Tested via mock inference contract checks and PIL verification. |
| `**/tools/infer_rtsp.py` | Live RTSP video capture loop which runs raw OpenCV frame streams. | Verified using mocked video captures and reconnect loops. |
| `**/tools/run_compare.py` | Run comparison depends on generated run artifacts and registry state. | Covered by run management, lineage ledger, and run comparison tool tests. |
| `**/tools/sync_to_mlflow.py` | Integration with external MLflow tracker API endpoints. | Verified using focused unit tests and API contract checks. |

---

## 5. Mutation Testing Gate

We use `mutmut` for mutation testing to verify the strength of our test suite.
- Mutation testing systematically modifies code statements (e.g. changing `<` to `<=`) and runs the
  test suite.
- If the test suite still passes, the mutant "survived", indicating a gap in test coverage or assertions.
- We target core algorithmic code under `src/fovux/core/` and require 0 surviving mutants in critical
  paths.

---

## 6. Performance Baselines

We track execution latency for key operations to prevent performance regressions.
- **Tools:** `pytest-benchmark` measures the operations per second (OPS) of critical functions.
- **Monitored Paths:** Duplicate image detection and dataset inspection pipelines.
- **Enforcement:** Benchmarks are run nightly to ensure operations do not degrade past established baseline durations.
