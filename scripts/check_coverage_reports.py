"""Validate backend Cobertura XML and Studio LCOV before external upload."""

from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BACKEND_MINIMUM_PERCENT = 85.0
DEFAULT_STUDIO_MINIMUM_PERCENT = 45.0


class CoverageReportError(ValueError):
    """Raised when a coverage report is missing, malformed, or misrouted."""


@dataclass(frozen=True)
class CoverageSummary:
    """Normalized report totals used by CI and tests."""

    name: str
    valid: int
    covered: int
    files: int

    @property
    def percent(self) -> float:
        """Return line coverage as a percentage."""
        return 100.0 * self.covered / self.valid


def _require_report(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise CoverageReportError(f"{label} coverage report is missing: {path}")
    if resolved.stat().st_size == 0:
        raise CoverageReportError(f"{label} coverage report is empty: {path}")
    return resolved


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _coverage_summary(
    *,
    name: str,
    valid: int,
    covered: int,
    files: int,
    minimum_percent: float,
) -> CoverageSummary:
    if valid <= 0:
        raise CoverageReportError(
            f"{name} coverage report contains no executable lines"
        )
    if covered < 0 or covered > valid:
        raise CoverageReportError(
            f"{name} coverage totals are invalid: covered={covered}, valid={valid}"
        )
    if files <= 0:
        raise CoverageReportError(f"{name} coverage report contains no source files")
    summary = CoverageSummary(name=name, valid=valid, covered=covered, files=files)
    if summary.percent < minimum_percent:
        raise CoverageReportError(
            f"{name} coverage {summary.percent:.2f}% is below required "
            f"{minimum_percent:.2f}%"
        )
    return summary


def _parse_nonnegative_int(value: str | None, *, label: str) -> int:
    try:
        parsed = int(value or "")
    except ValueError as exc:
        raise CoverageReportError(f"{label} is not an integer: {value!r}") from exc
    if parsed < 0:
        raise CoverageReportError(f"{label} must be non-negative")
    return parsed


def _resolve_backend_file(
    *,
    repo_root: Path,
    sources: list[Path],
    filename: str,
) -> Path:
    raw = Path(filename)
    if raw.is_absolute() or ".." in raw.parts:
        raise CoverageReportError(f"backend coverage path is unsafe: {filename}")
    candidates: list[Path] = []
    if raw.parts[:1] == ("fovux-mcp",):
        candidates.append(repo_root / raw)
    else:
        candidates.extend(source / raw for source in sources)
        candidates.append(repo_root / "fovux-mcp" / raw)
    expected_root = (repo_root / "fovux-mcp" / "src" / "fovux").resolve()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file() and _is_within(resolved, expected_root):
            return resolved
    raise CoverageReportError(
        f"backend coverage source does not map to fovux-mcp/src/fovux: {filename}"
    )


def validate_backend_report(
    *,
    repo_root: Path,
    report_path: Path,
    minimum_percent: float,
) -> CoverageSummary:
    """Validate one Cobertura XML report and its repository path mapping."""
    report = _require_report(report_path, "backend")
    try:
        root = ET.parse(report).getroot()  # noqa: S314 - local CI artifact
    except (ET.ParseError, OSError) as exc:
        raise CoverageReportError(f"backend coverage XML is invalid: {exc}") from exc
    if root.tag != "coverage":
        raise CoverageReportError("backend coverage XML root must be <coverage>")

    valid = _parse_nonnegative_int(root.get("lines-valid"), label="backend lines-valid")
    covered = _parse_nonnegative_int(
        root.get("lines-covered"), label="backend lines-covered"
    )
    source_nodes = [
        node.text.strip()
        for node in root.findall("./sources/source")
        if node.text and node.text.strip()
    ]
    sources = [
        (Path(value) if Path(value).is_absolute() else repo_root / value).resolve()
        for value in source_nodes
    ]
    if not sources:
        sources = [(repo_root / "fovux-mcp").resolve()]

    mapped_files = {
        _resolve_backend_file(
            repo_root=repo_root,
            sources=sources,
            filename=filename,
        )
        for element in root.findall(".//class")
        if (filename := element.get("filename"))
    }
    return _coverage_summary(
        name="backend",
        valid=valid,
        covered=covered,
        files=len(mapped_files),
        minimum_percent=minimum_percent,
    )


def _resolve_studio_file(*, repo_root: Path, source: str) -> Path:
    raw = Path(source)
    if raw.is_absolute():
        resolved = raw.resolve()
    elif raw.parts[:1] == ("fovux-studio",):
        resolved = (repo_root / raw).resolve()
    else:
        resolved = (repo_root / "fovux-studio" / raw).resolve()
    expected_root = (repo_root / "fovux-studio" / "src").resolve()
    if not resolved.is_file() or not _is_within(resolved, expected_root):
        raise CoverageReportError(
            f"Studio coverage source does not map to fovux-studio/src: {source}"
        )
    return resolved


def validate_studio_report(
    *,
    repo_root: Path,
    report_path: Path,
    minimum_percent: float,
) -> CoverageSummary:
    """Validate one LCOV report and its repository path mapping."""
    report = _require_report(report_path, "Studio")
    try:
        lines = report.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise CoverageReportError(f"Studio LCOV could not be read: {exc}") from exc

    current_source: Path | None = None
    mapped_files: set[Path] = set()
    executable_lines: set[tuple[Path, int]] = set()
    covered_lines: set[tuple[Path, int]] = set()
    for raw_line in lines:
        if raw_line.startswith("SF:"):
            current_source = _resolve_studio_file(
                repo_root=repo_root,
                source=raw_line.removeprefix("SF:").strip(),
            )
            mapped_files.add(current_source)
            continue
        if not raw_line.startswith("DA:"):
            continue
        if current_source is None:
            raise CoverageReportError(
                "Studio LCOV contains DA data before an SF record"
            )
        fields = raw_line.removeprefix("DA:").split(",")
        if len(fields) < 2:
            raise CoverageReportError(f"Studio LCOV DA record is malformed: {raw_line}")
        line_number = _parse_nonnegative_int(fields[0], label="Studio line number")
        hits = _parse_nonnegative_int(fields[1], label="Studio line hits")
        key = (current_source, line_number)
        executable_lines.add(key)
        if hits > 0:
            covered_lines.add(key)

    return _coverage_summary(
        name="Studio",
        valid=len(executable_lines),
        covered=len(covered_lines),
        files=len(mapped_files),
        minimum_percent=minimum_percent,
    )


def validate_reports(
    *,
    repo_root: Path,
    backend_report: Path,
    studio_report: Path,
    backend_minimum_percent: float = DEFAULT_BACKEND_MINIMUM_PERCENT,
    studio_minimum_percent: float = DEFAULT_STUDIO_MINIMUM_PERCENT,
) -> dict[str, CoverageSummary]:
    """Validate both reports against their explicit surface-specific floors."""
    root = repo_root.resolve()
    for name, minimum in (
        ("backend", backend_minimum_percent),
        ("Studio", studio_minimum_percent),
    ):
        if minimum <= 0 or minimum > 100:
            raise CoverageReportError(
                f"{name} minimum coverage must be greater than 0 and at most 100"
            )
    return {
        "backend": validate_backend_report(
            repo_root=root,
            report_path=backend_report,
            minimum_percent=backend_minimum_percent,
        ),
        "studio": validate_studio_report(
            repo_root=root,
            report_path=studio_report,
            minimum_percent=studio_minimum_percent,
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend-report",
        type=Path,
        default=REPO_ROOT / "fovux-mcp" / "coverage.xml",
    )
    parser.add_argument(
        "--studio-report",
        type=Path,
        default=REPO_ROOT / "fovux-studio" / "coverage" / "lcov.info",
    )
    parser.add_argument(
        "--backend-minimum-percent",
        type=float,
        default=DEFAULT_BACKEND_MINIMUM_PERCENT,
    )
    parser.add_argument(
        "--studio-minimum-percent",
        type=float,
        default=DEFAULT_STUDIO_MINIMUM_PERCENT,
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        summaries = validate_reports(
            repo_root=REPO_ROOT,
            backend_report=args.backend_report,
            studio_report=args.studio_report,
            backend_minimum_percent=args.backend_minimum_percent,
            studio_minimum_percent=args.studio_minimum_percent,
        )
    except CoverageReportError as exc:
        print(f"ERROR: {exc}")
        return 1
    details = ", ".join(
        f"{summary.name}={summary.percent:.2f}% "
        f"({summary.covered}/{summary.valid}, {summary.files} files)"
        for summary in summaries.values()
    )
    print(f"Coverage reports validated: {details}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
