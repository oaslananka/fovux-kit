"""dataset_find_duplicates — perceptual hash duplicate detection."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from fovux.core.dataset_utils import find_images, validate_recursive_scan_root
from fovux.core.errors import FovuxDatasetEmptyError, FovuxDatasetNotFoundError
from fovux.core.tooling import tool_event
from fovux.schemas.dataset import (
    DatasetFindDuplicatesInput,
    DatasetFindDuplicatesOutput,
    DuplicateGroup,
)
from fovux.server import mcp

logger = logging.getLogger(__name__)


@mcp.tool()
def dataset_find_duplicates(
    dataset_path: str,
    algorithm: str = "phash",
    hamming_threshold: int = 5,
    across_splits: bool = True,
) -> dict[str, Any]:
    """Find duplicate or near-duplicate images using perceptual hashing (phash/dhash/whash/avg).

    Returns duplicate groups sorted by size. Hamming threshold controls sensitivity.
    """
    inp = DatasetFindDuplicatesInput(
        dataset_path=Path(dataset_path),
        algorithm=algorithm,  # type: ignore[arg-type]
        hamming_threshold=hamming_threshold,
        across_splits=across_splits,
    )
    with tool_event(
        "dataset_find_duplicates",
        dataset_path=dataset_path,
        algorithm=algorithm,
        hamming_threshold=hamming_threshold,
    ):
        return _run_find_duplicates(inp).model_dump(mode="json")


def _run_find_duplicates(inp: DatasetFindDuplicatesInput) -> DatasetFindDuplicatesOutput:
    t0 = time.perf_counter()
    path = validate_recursive_scan_root(inp.dataset_path)

    if not path.exists():
        raise FovuxDatasetNotFoundError(str(path))

    images = find_images(path)
    if not images:
        raise FovuxDatasetEmptyError(str(path))

    import imagehash
    from PIL import Image

    hash_fn_map = {
        "phash": imagehash.phash,
        "dhash": imagehash.dhash,
        "whash": imagehash.whash,
        "avg": imagehash.average_hash,
    }
    hash_fn = hash_fn_map.get(inp.algorithm, imagehash.phash)

    hashes: list[tuple[Path, object, str]] = []
    for img_path in images:
        try:
            with Image.open(img_path) as im:
                h = hash_fn(im)
            hashes.append((img_path, h, _split_key(path, img_path)))
        except Exception as exc:
            logger.debug("Skipping unreadable image %s: %s", img_path, exc)
            continue

    # O(n²) comparison — acceptable for typical dataset sizes
    used: set[int] = set()
    groups: list[DuplicateGroup] = []

    for i, (p1, h1, split1) in enumerate(hashes):
        if i in used:
            continue
        group = [p1]
        max_distance = 0
        for j in range(i + 1, len(hashes)):
            if j in used:
                continue
            p2, h2, split2 = hashes[j]
            if not inp.across_splits and split1 != split2:
                continue
            dist = int(h1 - h2)  # type: ignore[operator]
            if dist <= inp.hamming_threshold:
                group.append(p2)
                used.add(j)
                max_distance = max(max_distance, dist)
        if len(group) > 1:
            used.add(i)
            groups.append(DuplicateGroup(images=group, hamming_distance=max_distance))

    groups.sort(key=lambda g: len(g.images), reverse=True)
    total_dup = sum(len(g.images) - 1 for g in groups)
    pct = round(total_dup / len(images) * 100, 2) if images else 0.0

    return DatasetFindDuplicatesOutput(
        total_images=len(images),
        duplicate_groups=groups,
        total_duplicates=total_dup,
        duplicate_pct=pct,
        analysis_duration_seconds=round(time.perf_counter() - t0, 3),
    )


def _split_key(dataset_root: Path, image_path: Path) -> str:
    """Return a stable split key for train/val/test-aware duplicate comparisons."""
    try:
        parts = image_path.relative_to(dataset_root).parts
    except ValueError:
        parts = image_path.parts

    split_mapping = {
        "train": "train",
        "val": "val",
        "valid": "val",
        "validation": "val",
        "dev": "val",
        "eval": "val",
        "test": "test",
    }
    for part in (part.lower() for part in parts):
        if part in split_mapping:
            return split_mapping[part]
    return "__unsplit__"
