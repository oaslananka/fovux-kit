"""Architecture guards for the Studio local HTTP service boundary."""

from __future__ import annotations

import ast
import io
from pathlib import Path

HTTP_ROOT = Path(__file__).parents[2] / "src/fovux/http"
ROUTE_LINE_BUDGET = 260
ROUTE_HANDLER_LINE_BUDGET = 60
SERVICE_LINE_BUDGET = 520
SERVICE_METHOD_LINE_BUDGET = 110


def _python_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(file for file in path.rglob("*.py") if file.name != "__pycache__")


def _imports_app(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "fovux.http.app":
            return True
        if isinstance(node, ast.Import):
            if any(alias.name == "fovux.http.app" for alias in node.names):
                return True
    return False


def test_thread_output_redirect_is_scoped() -> None:
    from fovux.http.thread_stream import redirect_thread_output

    captured = io.StringIO()
    with redirect_thread_output(captured):
        print("captured")

    assert captured.getvalue() == "captured\n"


def test_routes_and_services_never_import_application_factory() -> None:
    candidates = _python_files(HTTP_ROOT / "routes.py")
    candidates.extend(_python_files(HTTP_ROOT / "routes"))
    candidates.extend(_python_files(HTTP_ROOT / "services"))
    offenders = [str(path.relative_to(HTTP_ROOT)) for path in candidates if _imports_app(path)]
    assert offenders == []


def test_http_route_and_service_source_budgets() -> None:
    route_files = _python_files(HTTP_ROOT / "routes.py") + _python_files(HTTP_ROOT / "routes")
    service_files = _python_files(HTTP_ROOT / "services")
    assert route_files, "domain route modules must exist"
    assert service_files, "transport-neutral service modules must exist"

    failures: list[str] = []
    for path, file_budget, function_budget in (
        *((path, ROUTE_LINE_BUDGET, ROUTE_HANDLER_LINE_BUDGET) for path in route_files),
        *((path, SERVICE_LINE_BUDGET, SERVICE_METHOD_LINE_BUDGET) for path in service_files),
    ):
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        if len(lines) > file_budget:
            failures.append(f"{path.name}: {len(lines)} > {file_budget} lines")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.end_lineno:
                size = node.end_lineno - node.lineno + 1
                if size > function_budget:
                    failures.append(f"{path.name}:{node.name}: {size} > {function_budget} lines")
    assert failures == []
