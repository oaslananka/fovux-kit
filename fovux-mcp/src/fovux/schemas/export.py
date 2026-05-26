"""Pydantic schemas for export and quantization tools."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class ExportOnnxInput(BaseModel):
    """Input for export_onnx tool."""

    checkpoint: str
    output_path: Path | None = None
    imgsz: int = 640
    opset: int = 17
    dynamic: bool = False
    simplify: bool = True
    half: bool = False
    nms: bool = False
    device: str = "auto"
    parity_check: bool = True
    parity_tolerance: float = 1e-3


class ExportOnnxOutput(BaseModel):
    """Output from export_onnx tool."""

    checkpoint: str
    onnx_path: Path
    output_path: Path
    export_duration_seconds: float
    parity_passed: bool | None
    parity_max_diff: float | None
    file_size_mb: float
    opset: int
    model_size_bytes: int


class ExportTfliteInput(BaseModel):
    """Input for export_tflite tool."""

    checkpoint: str
    output_path: Path | None = None
    imgsz: int = 640
    half: bool = False
    int8: bool = False
    device: str = "auto"


class ExportTfliteOutput(BaseModel):
    """Output from export_tflite tool."""

    checkpoint: str
    tflite_path: Path
    output_path: Path
    export_duration_seconds: float
    file_size_mb: float
    model_size_bytes: int


class QuantizeInt8Input(BaseModel):
    """Input for quantize_int8 tool."""

    checkpoint: str
    calibration_dataset: Path
    output_path: Path | None = None
    imgsz: int = 640
    device: str = "auto"


class QuantizeInt8Output(BaseModel):
    """Output from quantize_int8 tool."""

    checkpoint: str
    quantized_path: Path
    quantize_duration_seconds: float
    model_size_bytes: int
    size_reduction_pct: float


class QuantizeReportInput(BaseModel):
    """Input for quantize_report tool."""

    original_checkpoint: str
    quantized_checkpoint: str
    dataset_path: Path
    split: str = "val"
    imgsz: int = 640
    device: str = "auto"
    max_map50_drop: float = 0.01
    strict: bool = False


class QuantizeReportOutput(BaseModel):
    """Output from quantize_report tool."""

    original_checkpoint: str
    quantized_checkpoint: str
    original_map50: float
    quantized_map50: float
    map50_delta: float
    verdict: str
    original_size_bytes: int
    quantized_size_bytes: int
    size_reduction_pct: float
    report_duration_seconds: float
