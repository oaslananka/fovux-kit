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


def test_create_app_accepts_explicit_service_container() -> None:
    from fovux.http.app import create_app
    from fovux.http.services.container import build_default_services

    services = build_default_services()
    app = create_app(services=services)

    assert app.state.http_services is services
    assert app.state.challenges is services.tool_runtime.challenges
    assert app.state.active_operation_tasks is services.operation_runtime.active_tasks


def test_domain_router_preserves_historical_paths_and_methods() -> None:
    from fovux.http.app import create_app

    expected = {
        "/datasets": {"GET"},
        "/datasets/{fingerprint}": {"GET"},
        "/events": {"GET"},
        "/exports": {"GET"},
        "/health": {"GET"},
        "/metrics": {"GET"},
        "/operations": {"POST"},
        "/operations/{id}": {"GET"},
        "/operations/{id}/cancel": {"POST"},
        "/operations/{id}/logs": {"GET"},
        "/operations/{id}/result": {"GET"},
        "/runs": {"GET"},
        "/runs/search": {"POST"},
        "/runs/{run_id}": {"GET"},
        "/runs/{run_id}/events": {"GET"},
        "/runs/{run_id}/lineage": {"GET"},
        "/runs/{run_id}/metrics": {"GET"},
        "/runs/{run_id}/stream": {"GET"},
        "/tools/{name}": {"POST"},
        "/tools/{name}/challenge": {"POST"},
    }
    schema = create_app().openapi()
    actual = {
        path: {
            method.upper()
            for method in operations
            if method.lower() in {"get", "post", "put", "patch", "delete"}
        }
        for path, operations in schema["paths"].items()
    }

    assert actual == expected
