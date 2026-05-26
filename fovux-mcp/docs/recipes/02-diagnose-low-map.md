# Recipe 02 — Diagnose Low mAP

1. Run `eval_run` on the checkpoint you suspect regressed.
2. Use `eval_per_class` to identify whether the drop is broad or concentrated.
3. Run `eval_error_analysis` to inspect likely causes such as small-object misses or class confusion.
4. Compare the run against a known-good baseline with `eval_compare` or `run_compare`.

This is the “why did performance fall?” recipe that turns raw metrics into next actions.
