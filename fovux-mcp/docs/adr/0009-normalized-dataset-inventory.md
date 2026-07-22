# ADR 0009: Normalized dataset inventory boundary

## Status

Accepted

## Context

Dataset inspection and validation previously contained separate, large YOLO and COCO branches. The
branches repeated image traversal, class accounting, bounding-box normalization, duplicate detection,
leakage analysis, and finding generation. This made equivalent behavior difficult to preserve across
formats and prevented `dataset_validate` from supporting COCO without another parallel implementation.

The public MCP tools and Pydantic result schemas are already consumed by Studio and external clients,
so the internal refactor must remain backward compatible.

## Decision

Introduce a transport-neutral `DatasetInventory` as the internal contract between format parsing and
dataset intelligence.

The dependency direction is:

1. YOLO and COCO adapters read format-specific metadata and files.
2. Adapters produce `DatasetInventory`, `ImageRecord`, `AnnotationRecord`, normalized bounding boxes,
   and format-neutral findings.
3. Shared analysis computes class statistics, annotation counts, box anomalies, duplicate groups, and
   train/validation/test leakage once.
4. `dataset_inspect` and `dataset_validate` map the shared results to the existing public output schemas.

Adapters implement the `DatasetFormatAdapter` protocol and are registered through
`register_dataset_adapter`. New formats may be added without importing tool modules or changing public
MCP schemas.

Bounding boxes use image-relative top-left/bottom-right coordinates internally. YOLO center-width-height
values are converted directly; COCO pixel values are normalized with declared or decoded image sizes.
Raw format values remain available for backward-compatible histograms and remediation reporting.

Image decoding and perceptual hashing are separately configurable. Validation decodes images without
computing fingerprints. Inspection enables fingerprints because duplicate and leakage intelligence
requires them. `max_images_analyzed` limits expensive decoding while inventory counts still represent
the complete dataset.

## Consequences

- YOLO and COCO now share statistics, anomaly, duplicate, leakage, and validation semantics.
- COCO gains deep validation without a second validation implementation.
- Public tool names, input schemas, output schemas, error envelopes, and security/path-policy behavior
  remain backward compatible.
- Format adapters own parsing only; tools own presentation only; shared analysis owns derived findings.
- The adapter registry is an explicit extension point, but adding a format still requires golden fixtures
  and compatibility tests before it is exposed publicly.
- COCO remediation remains explain-first. YOLO text-label clipping scripts are not emitted for COCO JSON.

## Validation

- Contract tests require YOLO and COCO adapters to produce the same normalized model.
- Golden fixtures cover healthy data, corrupt images, duplicate images, split leakage, Unicode paths,
  out-of-bounds boxes, and class mismatch.
- Architecture tests enforce dependency direction and source/function size budgets.
- Existing inspect, validate, public schema, path-policy, and security tests remain green.
- Benchmarks compare normalized inspection and adapter-only inventory construction on representative
  small and medium fixtures.
