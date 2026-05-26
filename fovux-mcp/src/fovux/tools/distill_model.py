"""distill_model — start a student run annotated with teacher metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.tooling import tool_event
from fovux.schemas.inference import DistillModelInput, DistillModelOutput
from fovux.schemas.training import TrainStartInput
from fovux.server import mcp
from fovux.tools.train_start import _run_train_start


@mcp.tool()
def distill_model(
    teacher_checkpoint: str,
    dataset_path: str,
    student_model: str = "yolov8n.pt",
    temperature: float = 4.0,
    alpha: float = 0.7,
    epochs: int = 100,
    batch: int = 16,
    imgsz: int = 640,
    device: str = "auto",
    name: str | None = None,
) -> dict[str, Any]:
    """Start a student-model training run with distillation metadata."""
    inp = DistillModelInput(
        teacher_checkpoint=teacher_checkpoint,
        student_model=student_model,
        dataset_path=Path(dataset_path),
        temperature=temperature,
        alpha=alpha,
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        name=name,
    )
    with tool_event("distill_model", teacher_checkpoint=teacher_checkpoint):
        return _run_distill_model(inp).model_dump(mode="json")


def _run_distill_model(inp: DistillModelInput) -> DistillModelOutput:
    teacher = resolve_checkpoint(inp.teacher_checkpoint)
    start = _run_train_start(
        TrainStartInput(
            dataset_path=inp.dataset_path,
            model=inp.student_model,
            epochs=inp.epochs,
            batch=inp.batch,
            imgsz=inp.imgsz,
            device=inp.device,
            name=inp.name,
            tags=["distillation"],
            extra_args={
                "teacher_checkpoint": str(teacher),
                "distillation_temperature": inp.temperature,
                "distillation_alpha": inp.alpha,
            },
        )
    )
    return DistillModelOutput(
        run_id=start.run_id,
        status=start.status,
        pid=start.pid,
        run_path=start.run_path,
        teacher_checkpoint=str(teacher),
        student_model=inp.student_model,
    )
