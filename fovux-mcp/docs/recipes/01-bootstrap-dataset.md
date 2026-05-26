# Recipe 01 — Bootstrap A Dataset

1. Run `dataset_inspect` to confirm image count, class count, and split structure.
2. Run `dataset_validate` to catch unreadable images, bbox range issues, and class-id errors.
3. Run `dataset_find_duplicates` if the source is stitched from multiple exports.
4. If needed, run `dataset_convert` or `dataset_split` before training.

This recipe is the fastest way to turn “I got a folder from someone else” into a trusted local training input.
