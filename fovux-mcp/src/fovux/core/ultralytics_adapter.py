"""Thin adapter around Ultralytics imports.

Keeps optional third-party imports out of tool modules and gives us a single
place to insulate runtime changes from the rest of the codebase.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Protocol, cast

from fovux.core.errors import FovuxError


class YoloModel(Protocol):
    """Minimal Ultralytics surface used by Fovux."""

    def export(self, **kwargs: object) -> object:
        """Export a model artifact."""

    def predict(self, **kwargs: object) -> list[object]:
        """Run model inference."""

    def train(self, **kwargs: object) -> object:
        """Train the model."""

    def val(self, **kwargs: object) -> object:
        """Evaluate the model."""


def get_yolo_class() -> type[Any]:
    """Return the Ultralytics YOLO class."""
    try:
        module = importlib.import_module("ultralytics")
        yolo_class = getattr(module, "YOLO", None)
        if yolo_class is None:
            raise AttributeError("ultralytics.YOLO is unavailable")
        return cast(type[Any], yolo_class)
    except Exception as exc:  # pragma: no cover - defensive import guard
        raise FovuxError(
            "Ultralytics is not available in the current environment.",
            hint="Install the `ultralytics` package to enable model operations.",
        ) from exc


def load_yolo_model(checkpoint: str | Path) -> YoloModel:
    """Instantiate a YOLO model from a checkpoint path or model name."""
    return cast(YoloModel, get_yolo_class()(str(checkpoint)))
