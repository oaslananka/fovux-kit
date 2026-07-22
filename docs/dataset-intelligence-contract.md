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
## Normalized inventory boundary

YOLO and COCO adapters populate the same internal `DatasetInventory` contract. Shared analysis owns
class statistics, normalized bounding-box findings, duplicate groups, and split leakage; inspect and
validate only map those results to their existing public schemas. The dependency direction and adapter
extension point are recorded in `fovux-mcp/docs/adr/0009-normalized-dataset-inventory.md`.

`dataset_validate` supports both YOLO and COCO. Golden coverage includes healthy fixtures plus corrupt
images, missing labels/images, malformed or out-of-bounds annotations, duplicate/leaked images, Unicode
paths, and class-registry mismatch.

## Performance evidence

A same-worker `pytest-benchmark` comparison on the bundled `mini_yolo` fixture measured the original
main implementation at 479.4 ms mean and the normalized-inventory implementation at 392.4 ms mean.
The metadata-only normalized adapters measured 111.1 ms for 40 YOLO images/annotations and 6.5 ms for
20 COCO images. These figures are evidence of no material regression, not hard timing gates; CI keeps
benchmark cases so trends can be compared without flaky wall-clock assertions.
