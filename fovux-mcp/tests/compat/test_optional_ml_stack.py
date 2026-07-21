"""Executable compatibility smoke tests for the optional Torch/Ultralytics stack."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest


def _enabled(name: str) -> bool:
    return os.environ.get(name) == "1"


def _prepare_ultralytics_config() -> None:
    """Use a writable config directory and avoid a network font download on Linux."""
    config_dir = Path(
        os.environ.setdefault(
            "YOLO_CONFIG_DIR",
            str(Path(tempfile.gettempdir()) / "fovux-ultralytics"),
        )
    )
    config_dir.mkdir(parents=True, exist_ok=True)
    font_target = config_dir / "Arial.ttf"
    font_source = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    if font_source.is_file() and not font_target.exists():
        shutil.copyfile(font_source, font_target)


_prepare_ultralytics_config()

pytestmark = [
    pytest.mark.skipif(
        not _enabled("FOVUX_TEST_OPTIONAL_ML"),
        reason="set FOVUX_TEST_OPTIONAL_ML=1 for optional ML smoke",
    ),
    pytest.mark.timeout(300),
]


def test_torch_213_stack_imports_and_runs_on_cpu(tmp_path: Path) -> None:
    """Torch, torchvision, Ultralytics, checkpoint loading, and CPU ops work."""
    import torch
    import torchvision
    from torchvision.ops import box_iou
    from ultralytics import YOLO

    assert torch.__version__.startswith("2.13.0")
    assert torchvision.__version__.startswith("0.28.0")

    left = torch.tensor([[1.0, 2.0]])
    right = torch.tensor([[3.0], [4.0]])
    assert torch.matmul(left, right).item() == pytest.approx(11.0)

    boxes = torch.tensor([[0.0, 0.0, 2.0, 2.0]])
    assert box_iou(boxes, boxes).item() == pytest.approx(1.0)

    checkpoint = tmp_path / "checkpoint.pt"
    torch.save({"tensor": left}, checkpoint)
    restored = torch.load(checkpoint, map_location="cpu", weights_only=True)
    assert torch.equal(restored["tensor"], left)

    model = YOLO("yolo11n.yaml")
    assert model.model is not None


def test_cuda_tensor_smoke_when_available() -> None:
    """Exercise CUDA when the selected runner exposes a working device."""
    import torch

    if not torch.cuda.is_available():
        pytest.skip("runner has no CUDA device")

    value = torch.tensor([2.0], device="cuda")
    assert (value * value).cpu().item() == pytest.approx(4.0)


@pytest.mark.skipif(
    not _enabled("FOVUX_TEST_YOLO_E2E"),
    reason="full YOLO smoke runs on the Linux compatibility lane",
)
def test_ultralytics_train_reload_and_onnx_export(tmp_path: Path) -> None:
    """Train a tiny model, reload its checkpoint, and export it to ONNX."""
    from PIL import Image
    from ultralytics import YOLO

    dataset = tmp_path / "dataset"
    for split in ("train", "val"):
        image_dir = dataset / "images" / split
        label_dir = dataset / "labels" / split
        image_dir.mkdir(parents=True)
        label_dir.mkdir(parents=True)
        Image.new("RGB", (64, 64), color=(127, 127, 127)).save(image_dir / "sample.jpg")
        (label_dir / "sample.txt").write_text("0 0.5 0.5 0.5 0.5\n", encoding="utf-8")

    data_yaml = dataset / "data.yaml"
    data_yaml.write_text(
        "path: " + dataset.as_posix() + "\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n  0: object\n",
        encoding="utf-8",
    )

    run_dir = tmp_path / "runs"
    model = YOLO("yolo11n.yaml")
    result = model.train(
        data=str(data_yaml),
        epochs=1,
        imgsz=64,
        batch=1,
        device="cpu",
        workers=0,
        project=str(run_dir),
        name="smoke",
        exist_ok=True,
        cache=False,
        plots=False,
        save=True,
        verbose=False,
    )
    assert result is not None

    checkpoint = run_dir / "smoke" / "weights" / "best.pt"
    assert checkpoint.is_file()
    reloaded = YOLO(str(checkpoint))
    exported = Path(
        reloaded.export(
            format="onnx",
            imgsz=64,
            device="cpu",
            simplify=False,
            dynamic=False,
            opset=17,
        )
    )
    assert exported.is_file()
    assert exported.suffix == ".onnx"
