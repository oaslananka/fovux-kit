# Dashboard Resilience Contract

Fovux Studio dashboard must remain useful during long training runs and temporary backend failures.

## Required behavior

- Metric streaming or refresh failures show a reconnecting/polling fallback state.
- Offline backend state is explicit and keeps cached runs visible when possible.
- Malformed metric payloads are ignored instead of breaking charts.
- Run state UI must expose running, stopped, failed, resumed/resumable, and completed states through run summaries and actions.
- Run comparison must cover key metrics, artifacts/report paths, config diffs, model cards, and regression/frontier indicators.

## Verification

`python scripts/check_dashboard_resilience.py` validates dashboard fallback strings, malformed metric guards,
run action wiring, compare-run result fields, and tests for stale/malformed/offline scenarios.
