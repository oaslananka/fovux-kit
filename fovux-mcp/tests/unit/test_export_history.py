"""Tests for export history JSONL helpers."""

from __future__ import annotations

from pathlib import Path

from fovux.core.export_history import (
    exports_history_path,
    read_export_history,
    record_export_history,
)


def test_record_and_read_export_history(tmp_fovux_home: Path) -> None:
    """Export history should append JSONL entries and read the newest entries."""
    first = record_export_history(
        source_checkpoint=Path("runs/a/weights/best.pt"),
        artifact_path=Path("exports/a.onnx"),
        format="onnx",
        duration_s=1.23456789,
        metadata={"parity_passed": True},
    )
    second = record_export_history(
        source_checkpoint=Path("runs/b/weights/best.pt"),
        artifact_path=Path("exports/b.tflite"),
        format="tflite",
        duration_s=2.0,
    )

    entries = read_export_history()

    assert exports_history_path() == tmp_fovux_home / "exports.jsonl"
    assert entries[0]["id"] == first["id"]
    assert entries[0]["duration_s"] == 1.234568
    assert entries[0]["parity_passed"] is True
    assert entries[1]["id"] == second["id"]


def test_read_export_history_ignores_bad_lines_and_applies_limit(tmp_fovux_home: Path) -> None:
    """Corrupt lines should be ignored and limit should keep the newest entries."""
    history_path = tmp_fovux_home / "exports.jsonl"
    history_path.write_text(
        '{"id": "old"}\nnot-json\n[]\n{"id": "new"}\n',
        encoding="utf-8",
    )

    assert read_export_history(limit=1) == [{"id": "new"}]
