"""Generate minimal test fixture datasets.

Run this script once after installing dev dependencies to populate
tests/fixtures/mini_yolo/ and tests/fixtures/mini_coco/.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

FIXTURES = Path(__file__).parent.parent / "tests" / "fixtures"
SEED = 42
random.seed(SEED)


def make_tiny_image(
    path: Path,
    w: int = 64,
    h: int = 64,
    color: tuple[int, int, int] = (128, 128, 128),
    index: int = 0,
) -> None:
    """Create a small deterministic image fixture with a distinct visual fingerprint."""
    import numpy as np

    rng = np.random.default_rng(seed=index * 1000 + sum(color))
    # Unique noise-based background ensures every image has a distinct pHash
    arr = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
    # Blend with base color so class identity is still visible
    arr = (arr * 0.4 + np.array(color, dtype=np.float32) * 0.6).astype(np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    x0, y0 = int(w * 0.15), int(h * 0.15)
    x1, y1 = int(w * 0.55), int(h * 0.55)
    rect_color = ((100 + index * 37) % 200, (50 + index * 53) % 200, (80 + index * 61) % 200)
    draw.rectangle([x0, y0, x1, y1], fill=tuple(rect_color))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), "JPEG")


def make_yolo_label(
    path: Path,
    class_id: int,
    x: float = 0.35,
    y: float = 0.35,
    bw: float = 0.3,
    bh: float = 0.3,
) -> None:
    """Write a single normalized YOLO label row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{class_id} {x:.4f} {y:.4f} {bw:.4f} {bh:.4f}\n")


def create_mini_yolo() -> None:
    """Generate the minimal YOLO fixture used by fast local and CI tests."""
    print("Creating mini_yolo fixture...")
    root = FIXTURES / "mini_yolo"

    (root / "images" / "train").mkdir(parents=True, exist_ok=True)
    (root / "images" / "val").mkdir(parents=True, exist_ok=True)
    (root / "labels" / "train").mkdir(parents=True, exist_ok=True)
    (root / "labels" / "val").mkdir(parents=True, exist_ok=True)

    (root / "data.yaml").write_text(
        "path: .\ntrain: images/train\nval: images/val\nnc: 2\nnames: ['cat', 'dog']\n"
    )

    for i in range(30):
        cls = i % 2
        color: tuple[int, int, int] = (200, 100, 100) if cls == 0 else (100, 100, 200)
        make_tiny_image(root / "images" / "train" / f"{i:03d}.jpg", color=color, index=i)
        make_yolo_label(root / "labels" / "train" / f"{i:03d}.txt", cls)

    for i in range(10):
        cls = i % 2
        color = (200, 100, 100) if cls == 0 else (100, 100, 200)
        make_tiny_image(root / "images" / "val" / f"{i:03d}.jpg", color=color, index=i + 30)
        make_yolo_label(root / "labels" / "val" / f"{i:03d}.txt", cls)

    print("  mini_yolo: 30 train + 10 val images, 2 classes")


def create_mini_coco() -> None:
    """Generate the compact COCO fixture used by conversion and evaluation tests."""
    print("Creating mini_coco fixture...")
    root = FIXTURES / "mini_coco"
    images_dir = root / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    (root / "annotations").mkdir(parents=True, exist_ok=True)

    coco: dict = {
        "info": {"description": "Mini COCO fixture", "version": "1.0"},
        "categories": [
            {"id": 1, "name": "cat", "supercategory": "animal"},
            {"id": 2, "name": "dog", "supercategory": "animal"},
        ],
        "images": [],
        "annotations": [],
    }

    ann_id = 1
    for i in range(20):
        cls_id = (i % 2) + 1
        color: tuple[int, int, int] = (200, 100, 100) if cls_id == 1 else (100, 100, 200)
        make_tiny_image(images_dir / f"{i:03d}.jpg", color=color)
        coco["images"].append({"id": i, "file_name": f"{i:03d}.jpg", "width": 64, "height": 64})
        coco["annotations"].append(
            {
                "id": ann_id,
                "image_id": i,
                "category_id": cls_id,
                "bbox": [10, 10, 20, 20],
                "area": 400,
                "iscrowd": 0,
            }
        )
        ann_id += 1

    ann_path = root / "annotations" / "instances_train.json"
    ann_path.write_text(json.dumps(coco, indent=2))
    print("  mini_coco: 20 images, 2 classes")


def create_corrupt_samples() -> None:
    """Generate intentionally invalid image files for negative-path tests."""
    print("Creating corrupt_samples fixture...")
    corrupt_dir = FIXTURES / "corrupt_samples"
    corrupt_dir.mkdir(parents=True, exist_ok=True)
    (corrupt_dir / "corrupt.jpg").write_bytes(b"not an image at all")
    (corrupt_dir / "empty.jpg").write_bytes(b"")
    print("  corrupt_samples: 2 corrupt files")


if __name__ == "__main__":
    create_mini_yolo()
    create_mini_coco()
    create_corrupt_samples()
    print("Done! Fixtures ready in tests/fixtures/")
