# Review Queue Contract

Fovux provides a local review queue for model-assisted annotation workflows.

## Workflow

1. `active_learning_queue_rank` scores local images from a dataset and checkpoint.
2. Ranked entries are stored with image path, score, reason, and predictions.
3. `active_learning_queue_list` returns pending entries.
4. Studio opens the annotation editor in queue mode and shows score, reason, predictions, and save split.
5. `active_learning_queue_submit` writes reviewed labels into the selected train/val/test split and marks the entry reviewed.
6. Reviewers can skip entries without writing labels.

Reason codes include `low_confidence`, `disagreement`, `outlier`, `underrepresented_class`, and `no_detections`.

The queue is local-first and uses local paths, local checkpoints, local predictions, and the local SQLite registry.
