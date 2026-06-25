"""demo_init — initialize a demo workspace for onboarding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from fovux.core.paths import ensure_fovux_dirs, get_fovux_home
from fovux.core.runs import get_registry
from fovux.core.tooling import tool_event
from fovux.schemas.management import DemoInitInput, DemoInitOutput
from fovux.server import mcp


@mcp.tool()
def demo_init(target_path: str = "demo_workspace") -> dict[str, Any]:
    """Initialize a demo workspace with lightweight dataset, mock runs, and models.

    Args:
        target_path: Target directory path (absolute or relative to FOVUX_HOME).
    """
    inp = DemoInitInput(target_path=target_path)
    with tool_event("demo_init", target_path=target_path):
        output = _run_demo_init(inp)
        return output.model_dump(mode="json")


def _run_demo_init(inp: DemoInitInput) -> DemoInitOutput:
    paths = ensure_fovux_dirs(get_fovux_home())
    registry = get_registry(paths.runs_db)

    # 1. Resolve target path
    target = Path(inp.target_path).expanduser()
    if not target.is_absolute():
        target = (paths.home / target).resolve()

    dataset_dir = target / "sample_dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # 2. Write data.yaml
    (dataset_dir / "data.yaml").write_text(
        "path: .\ntrain: images/train\nval: images/val\nnc: 2\nnames: ['cat', 'dog']\n",
        encoding="utf-8",
    )

    # 3. Create helper for making deterministic sample images
    def _make_sample_image(path: Path, color: tuple[int, int, int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", (64, 64), color)
        draw = ImageDraw.Draw(img)
        # Bounding box is [10, 10, 30, 30] which gives center_x=0.3125, center_y=0.3125
        draw.rectangle((10.0, 10.0, 30.0, 30.0), fill=(100, 200, 100))
        img.save(str(path), "JPEG")

    def _make_label(path: Path, class_id: int) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{class_id} 0.3125 0.3125 0.3125 0.3125\n", encoding="utf-8")

    # 4. Generate dataset images/labels
    _make_sample_image(dataset_dir / "images" / "train" / "000.jpg", (200, 100, 100))
    _make_label(dataset_dir / "labels" / "train" / "000.txt", 0)

    _make_sample_image(dataset_dir / "images" / "train" / "001.jpg", (100, 100, 200))
    _make_label(dataset_dir / "labels" / "train" / "001.txt", 1)

    _make_sample_image(dataset_dir / "images" / "val" / "000.jpg", (200, 100, 100))
    _make_label(dataset_dir / "labels" / "val" / "000.txt", 0)

    # 5. Save a model checkpoint
    paths.models.mkdir(parents=True, exist_ok=True)
    yolov8n_pt = paths.models / "yolov8n.pt"
    yolov8n_pt.write_bytes(b"dummy yolo base weights")

    # 6. Create a mock run
    run_id = "demo_run_01"
    run_dir = paths.run_dir(run_id)
    run_dir.mkdir(parents=True, exist_ok=True)

    weights_dir = run_dir / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    best_pt = weights_dir / "best.pt"
    best_pt.write_bytes(b"dummy yolo model best weights")
    last_pt = weights_dir / "last.pt"
    last_pt.write_bytes(b"dummy yolo model last weights")

    # Save training params
    (run_dir / "params.json").write_text(
        '{"model": "yolov8n.pt", "epochs": 10, "batch": 16, "imgsz": 64, "device": "cpu"}',
        encoding="utf-8",
    )

    # Register run
    registry.create_run(
        run_id=run_id,
        run_path=run_dir,
        model="yolov8n.pt",
        dataset_path=dataset_dir,
        task="detect",
        epochs=10,
        tags=["demo", "baseline"],
    )
    registry.update_status(run_id=run_id, status="complete")

    # 7. Record mock metrics
    for epoch in range(1, 11):
        map50 = 0.45 + (0.40 * (epoch / 10.0))
        box_loss = 1.6 - (1.2 * (epoch / 10.0))
        registry.add_metric(run_id=run_id, epoch=epoch, key="metrics/mAP50(B)", value=map50)
        registry.add_metric(run_id=run_id, epoch=epoch, key="train/box_loss", value=box_loss)

    # 8. Record mock export
    paths.exports.mkdir(parents=True, exist_ok=True)
    best_onnx = paths.exports / "demo_model.onnx"
    best_onnx.write_bytes(b"dummy onnx weights")

    registry.record_export(
        export_id="export_demo_01",
        run_id=run_id,
        source_checkpoint=best_pt,
        artifact_path=best_onnx,
        format="onnx",
        duration_s=1.2,
        validation_result={"status": "passed", "readiness_score": 95},
    )

    (target / "README.md").write_text(
        "# Fovux Demo Workspace\n\n"
        "Open sample_dataset/data.yaml, inspect the dataset, review demo_run_01, "
        "and export demo_model.onnx without network access.\n",
        encoding="utf-8",
    )

    return DemoInitOutput(
        dataset_path=dataset_dir,
        run_id=run_id,
        run_path=run_dir,
        model_path=yolov8n_pt,
        export_path=best_onnx,
    )
