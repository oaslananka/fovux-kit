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

## 2. Code Coverage Omit List & Rationales

To maintain a meaningful coverage gate (minimum 90% required on included files), we exclude
certain entry points and integration-heavy adapters where line-by-line coverage checks produce
brittle or low-value tests. Below is the list of omitted paths and their rationales:

| Excluded File/Pattern | Rationale | How It Is Verified |
| :--- | :--- | :--- |
| `**/__main__.py` | CLI/Module entry point. Contains only bootstrap boilerplate. | Covered via CLI command execution smoke tests. |
| `**/cli.py` | Typer command-line interface logic. Primarily configuration and parsing. | Verified via end-to-end subprocess tests in the test suite. |
| `**/core/train_worker.py` | Detached backend worker process logic designed to run in a separate process. | Tested via mock subprocess spawning tests and E2E training logs. |
| `**/core/ultralytics_adapter.py` | Third-party Ultralytics library adapter wrapper. | Checked indirectly via training, eval, and inference tool suites. |
| `**/tools/export_tflite.py` | Integration with external TensorFlow/Keras libraries for compilation. | Covered by mock integration tests verifying correct exported file paths. |
| `**/tools/infer_image.py` | YOLO prediction pipeline that interacts with model weights. | Tested via mock inference contract checks and PIL verification. |
| `**/tools/infer_rtsp.py` | Live RTSP video capture loop which runs raw OpenCV frame streams. | Verified using mocked video captures and reconnect loops. |
| `**/tools/sync_to_mlflow.py` | Integration with external MLflow tracker API endpoints. | Verified using focused unit tests and API contract checks. |

---

## 3. Mutation Testing Gate

We use `mutmut` for mutation testing to verify the strength of our test suite.
- Mutation testing systematically modifies code statements (e.g. changing `<` to `<=`) and runs the
  test suite.
- If the test suite still passes, the mutant "survived", indicating a gap in test coverage or assertions.
- We target core algorithmic code under `src/fovux/core/` and require 0 surviving mutants in critical
  paths.

---

## 4. Performance Baselines

We track execution latency for key operations to prevent performance regressions.
- **Tools:** `pytest-benchmark` measures the operations per second (OPS) of critical functions.
- **Monitored Paths:** Duplicate image detection and dataset inspection pipelines.
- **Enforcement:** Benchmarks are run nightly to ensure operations do not degrade past established baseline durations.
