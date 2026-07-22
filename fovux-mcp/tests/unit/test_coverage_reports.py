"""Tests for deterministic backend and Studio coverage report validation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "check_coverage_reports.py"


def _load_module() -> ModuleType:
    assert SCRIPT.exists(), "coverage report validator is missing"
    spec = importlib.util.spec_from_file_location("check_coverage_reports", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_source_tree(root: Path) -> None:
    backend = root / "fovux-mcp" / "src" / "fovux"
    studio = root / "fovux-studio" / "src"
    backend.mkdir(parents=True)
    studio.mkdir(parents=True)
    (backend / "example.py").write_text("value = 1\n", encoding="utf-8")
    (studio / "example.ts").write_text("export const value = 1;\n", encoding="utf-8")


def _write_backend_report(root: Path, *, valid: int = 10, covered: int = 9) -> Path:
    report = root / "fovux-mcp" / "coverage.xml"
    rate = covered / valid
    report.write_text(
        f'''<?xml version="1.0" ?>
<coverage lines-valid="{valid}" lines-covered="{covered}" line-rate="{rate}">
  <sources><source>{root / "fovux-mcp"}</source></sources>
  <packages><package name="src.fovux"><classes>
    <class name="example.py" filename="src/fovux/example.py">
      <lines><line number="1" hits="1" /></lines>
    </class>
  </classes></package></packages>
</coverage>
''',
        encoding="utf-8",
    )
    return report


def _write_studio_report(
    root: Path,
    *,
    source: str = "src/example.ts",
    covered: int = 9,
    valid: int = 10,
) -> Path:
    report = root / "fovux-studio" / "coverage" / "lcov.info"
    report.parent.mkdir(parents=True)
    lines = ["TN:", f"SF:{source}"]
    lines.extend(f"DA:{line},{1 if line <= covered else 0}" for line in range(1, valid + 1))
    lines.extend([f"LF:{valid}", f"LH:{covered}", "end_of_record", ""])
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def test_valid_reports_are_separated_and_meet_threshold(tmp_path: Path) -> None:
    module = _load_module()
    _write_source_tree(tmp_path)

    summaries = module.validate_reports(
        repo_root=tmp_path,
        backend_report=_write_backend_report(tmp_path),
        studio_report=_write_studio_report(tmp_path),
        backend_minimum_percent=85.0,
        studio_minimum_percent=45.0,
    )

    assert summaries["backend"].percent == pytest.approx(90.0)
    assert summaries["studio"].percent == pytest.approx(90.0)
    assert summaries["backend"].files == 1
    assert summaries["studio"].files == 1


def test_missing_or_empty_reports_fail_before_upload(tmp_path: Path) -> None:
    module = _load_module()
    _write_source_tree(tmp_path)
    backend = _write_backend_report(tmp_path)
    studio = tmp_path / "fovux-studio" / "coverage" / "lcov.info"
    studio.parent.mkdir(parents=True)
    studio.write_text("", encoding="utf-8")

    with pytest.raises(module.CoverageReportError, match="empty"):
        module.validate_reports(
            repo_root=tmp_path,
            backend_report=backend,
            studio_report=studio,
            backend_minimum_percent=85.0,
            studio_minimum_percent=45.0,
        )


def test_misrouted_studio_source_is_rejected(tmp_path: Path) -> None:
    module = _load_module()
    _write_source_tree(tmp_path)

    backend = _write_backend_report(tmp_path)
    studio = _write_studio_report(tmp_path, source="../fovux-mcp/src/fovux/example.py")

    with pytest.raises(module.CoverageReportError, match="fovux-studio/src"):
        module.validate_reports(
            repo_root=tmp_path,
            backend_report=backend,
            studio_report=studio,
            backend_minimum_percent=85.0,
            studio_minimum_percent=45.0,
        )


def test_report_below_required_threshold_is_rejected(tmp_path: Path) -> None:
    module = _load_module()
    _write_source_tree(tmp_path)

    backend = _write_backend_report(tmp_path, covered=8)
    studio = _write_studio_report(tmp_path)

    with pytest.raises(module.CoverageReportError, match="below required 85.00%"):
        module.validate_reports(
            repo_root=tmp_path,
            backend_report=backend,
            studio_report=studio,
            backend_minimum_percent=85.0,
            studio_minimum_percent=45.0,
        )


def test_studio_report_below_surface_floor_is_rejected(tmp_path: Path) -> None:
    module = _load_module()
    _write_source_tree(tmp_path)

    backend = _write_backend_report(tmp_path)
    studio = _write_studio_report(tmp_path, covered=4)

    with pytest.raises(module.CoverageReportError, match="below required 45.00%"):
        module.validate_reports(
            repo_root=tmp_path,
            backend_report=backend,
            studio_report=studio,
            backend_minimum_percent=85.0,
            studio_minimum_percent=45.0,
        )
