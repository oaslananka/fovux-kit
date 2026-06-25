"""Validate review queue contracts."""
from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")

def main() -> int:
    failures: list[str] = []
    schema = _read(ROOT / "fovux-mcp" / "src" / "fovux" / "schemas" / "inference.py")
    for phrase in ["ActiveLearningQueueItem", "score", "reason", "predictions", "dataset_split", "queue_entries"]:
        if phrase not in schema:
            failures.append(f"Queue schema missing {phrase}")
    tools_dir = ROOT / "fovux-mcp" / "src" / "fovux" / "tools"
    for suffix in ["rank", "list", "submit"]:
        path = tools_dir / f"active_learning_queue_{suffix}.py"
        if not path.exists():
            failures.append(f"Missing queue tool file: {suffix}")
    rank = _read(tools_dir / "active_learning_queue_rank.py")
    for phrase in ["low_confidence", "disagreement", "outlier", "underrepresented_class", "no_detections"]:
        if phrase not in rank:
            failures.append(f"Ranking reason missing {phrase}")
    submit = _read(tools_dir / "active_learning_queue_submit.py")
    for phrase in ["update_review_queue_status", "labels_dir", "images_dir", "dataset_split"]:
        if phrase not in submit:
            failures.append(f"Submit flow missing {phrase}")
    studio = _read(ROOT / "fovux-studio" / "src" / "commands" / "openAnnotationEditor.ts")
    for phrase in ["active_learning_queue_list", "active_learning_queue_submit", "queueReason", "queueScore", "queueEntryId"]:
        if phrase not in studio:
            failures.append(f"Studio queue wiring missing {phrase}")
    tests = _read(ROOT / "fovux-mcp" / "tests" / "unit" / "tools" / "test_active_learning_queue.py")
    for phrase in ["rank_inserts_to_db", "list_retrieves_items", "submit_writes_labels", "underrepresented", "disagreement", "outliers"]:
        if phrase not in tests:
            failures.append(f"Queue tests missing {phrase}")
    docs = _read(ROOT / "docs" / "review-queue-contract.md")
    for phrase in ["active_learning_queue_rank", "active_learning_queue_list", "active_learning_queue_submit", "low_confidence", "local-first"]:
        if phrase not in docs:
            failures.append(f"Queue docs missing {phrase}")
    if failures:
        for failure in failures:
            print(failure)
        return 1
    print("Review queue checks passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
