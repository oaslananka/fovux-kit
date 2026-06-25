# Dataset Intelligence Contract

Fovux dataset tools must detect the common issues that block safe training and must return both
structured JSON and human-readable remediation guidance.

## Required coverage

| Failure mode | Tool coverage | Expected output |
| --- | --- | --- |
| Missing images or labels | `dataset_validate`, `dataset_inspect` | errors/warnings plus remediation script or auto-fix plan |
| Malformed YOLO labels | `dataset_validate` | structured errors and safe remediation guidance |
| Out-of-bounds boxes | `dataset_validate`, `annotation_quality_check` | errors and bounded-box remediation |
| Empty labels | `dataset_validate`, `annotation_quality_check` | warning/error entry and cleanup guidance |
| Duplicate images | `dataset_find_duplicates`, `dataset_inspect` | duplicate groups and auto-fix plan |
| Train/val/test leakage | `dataset_inspect`, `dataset_find_duplicates` | leakage issues and split cleanup plan |
| Class imbalance | `dataset_inspect` | Gini score, quality score, and rebalance suggestion |
| Tiny/huge boxes | `annotation_quality_check`, `dataset_inspect` | anomaly counts and review suggestion |

## Agent-facing output

- `dataset_validate` returns structured `errors`, `warnings`, `valid`, and `remediation_script`.
- `dataset_inspect` returns `quality_score`, `dataset_card`, `class_balance_gini`, leakage data,
  duplicate counts, and `auto_fix_plan` actions.
- `dataset_find_duplicates` returns duplicate groups and split-aware results.
- Golden dataset tests create deterministic fixtures for corrupt files, missing labels, malformed labels,
  class mismatch, duplicate images, split leakage, and path-normalization edge cases.

## Safe remediation

Remediation output must be explain-first and non-destructive by default. Generated scripts or suggested
commands must be optional and scoped to the supplied dataset path.
