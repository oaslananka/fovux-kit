"""Tests for HTTP routes and SSE metric streaming."""

from __future__ import annotations

import asyncio
import json
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from fovux.core.errors import FovuxDatasetNotFoundError
from fovux.core.paths import ensure_fovux_dirs
from fovux.core.runs import RunRegistry
from fovux.http.app import create_app
from fovux.http.routes import (
    _load_metric_payload_delta,
    _load_metric_payloads,
    _load_metrics_jsonl,
    _metric_event_stream,
    _pop_fresh_tool_operation_result,
    _prune_tool_operation_results,
    _release_semaphore_after_worker,
    _remember_timed_out_tool_worker,
    _resolve_run_dir,
    _tool_operation_id,
)
from fovux.http.tool_proxy import HTTP_TOOL_POLICIES, HttpToolPolicy


def _seed_run(tmp_fovux_home: Path, run_id: str = "run_stream") -> tuple[Path, RunRegistry]:
    paths = ensure_fovux_dirs(tmp_fovux_home)
    registry = RunRegistry(paths.runs_db)
    run_dir = paths.runs / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    registry.create_run(
        run_id=run_id,
        run_path=run_dir,
        model="yolov8n.pt",
        dataset_path=tmp_fovux_home / "dataset",
        task="detect",
        epochs=2,
        tags=[],
    )
    registry.update_status(run_id, "running", pid=1234)
    return run_dir, registry


def _auth_headers(client: TestClient) -> dict[str, str]:
    token = str(client.app.state.auth_token)
    return {"Authorization": f"Bearer {token}"}


def test_metrics_sse_streams_appended_rows(tmp_fovux_home: Path) -> None:
    """Metric event stream should emit newly appended rows."""
    run_dir, _registry = _seed_run(tmp_fovux_home)
    metrics_jsonl = run_dir / "metrics.jsonl"
    metrics_jsonl.write_text(
        '{"run_id": "run_stream", "epoch": 1, "metrics": {"metrics/mAP50(B)": 0.42}}\n',
        encoding="utf-8",
    )

    async def disconnected() -> bool:
        return False

    async def consume_stream() -> list[dict[str, object]]:
        shutdown_event = asyncio.Event()
        payloads: list[dict[str, object]] = []
        initial_size = metrics_jsonl.stat().st_size

        stream = _metric_event_stream(
            run_id="run_stream",
            run_dir=run_dir,
            disconnect_check=disconnected,
            shutdown_event=shutdown_event,
        )
        retry = await anext(stream)
        assert retry == "retry: 5000\n\n"
        first = await anext(stream)
        payloads.append(json.loads(first.split("data: ", maxsplit=1)[1]))
        with metrics_jsonl.open("a", encoding="utf-8") as handle:
            handle.write(
                '{"run_id": "run_stream", "epoch": 2, "metrics": {"metrics/mAP50(B)": 0.55}}\n'
            )
        _, _, delta_payloads = _load_metric_payload_delta(
            "run_stream",
            run_dir,
            emitted_count=1,
            previous_offset=initial_size,
        )
        payloads.extend(delta_payloads)
        shutdown_event.set()
        await stream.aclose()
        return payloads

    payloads = asyncio.run(consume_stream())
    assert [payload["epoch"] for payload in payloads] == [1, 2]
    assert payloads[-1]["runId"] == "run_stream"


def test_metrics_sse_missing_run_returns_404(tmp_fovux_home: Path) -> None:
    """Unknown run IDs should return 404 from the metrics endpoint."""
    with TestClient(create_app()) as client:
        response = client.get("/runs/does-not-exist/metrics", headers=_auth_headers(client))
    assert response.status_code == 404


def test_stream_endpoint_emits_terminal_done_event(tmp_fovux_home: Path) -> None:
    """The canonical SSE endpoint should close with a done event for terminal runs."""
    run_dir, _registry = _seed_run(tmp_fovux_home, run_id="run_done")
    (run_dir / "status.json").write_text('{"status": "completed"}', encoding="utf-8")
    (run_dir / "metrics.jsonl").write_text(
        '{"run_id": "run_done", "epoch": 1, "metrics": {"metrics/mAP50(B)": 0.66}}\n',
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.get("/runs/run_done/stream", headers=_auth_headers(client))

    assert response.status_code == 200
    assert "event: metric" in response.text
    assert "event: done" in response.text


def test_stream_endpoint_requires_auth(tmp_fovux_home: Path) -> None:
    """Run metric streams should keep the same auth behavior as other run endpoints."""
    _seed_run(tmp_fovux_home, run_id="run_auth")

    with TestClient(create_app()) as client:
        response = client.get("/runs/run_auth/stream")

    assert response.status_code == 401


def test_tool_proxy_invokes_local_tool(tmp_fovux_home: Path) -> None:
    """POST /tools/{name} should proxy to the local tool implementation."""
    with TestClient(create_app()) as client:
        response = client.post("/tools/model_list", json={}, headers=_auth_headers(client))
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0


def test_health_endpoint_returns_version(tmp_fovux_home: Path) -> None:
    """The health endpoint should advertise a healthy server and package version."""
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_vscode_webview_origin_can_preflight_authenticated_routes(
    tmp_fovux_home: Path,
) -> None:
    """VS Code webviews should be allowed to call the local authenticated API."""
    with TestClient(create_app()) as client:
        response = client.options(
            "/runs",
            headers={
                "Origin": "vscode-webview://fovux-demo",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "vscode-webview://fovux-demo"
    assert "Authorization" in response.headers["access-control-allow-headers"]


def test_prometheus_metrics_requires_explicit_enable(tmp_fovux_home: Path) -> None:
    """The Prometheus snapshot endpoint should be opt-in."""
    with TestClient(create_app()) as client:
        disabled = client.get("/metrics", headers=_auth_headers(client))

    assert disabled.status_code == 404

    _seed_run(tmp_fovux_home, run_id="run_metrics_endpoint")
    with TestClient(create_app(enable_metrics=True)) as client:
        enabled = client.get("/metrics", headers=_auth_headers(client))

    assert enabled.status_code == 200
    assert "fovux_active_runs 1" in enabled.text


def test_list_runs_returns_seeded_records(tmp_fovux_home: Path) -> None:
    """Run listing should surface seeded registry records."""
    _seed_run(tmp_fovux_home, run_id="run_listed")

    with TestClient(create_app()) as client:
        response = client.get("/runs", headers=_auth_headers(client))

    assert response.status_code == 200
    payload = response.json()[0]
    assert payload["id"] == "run_listed"
    assert "current_epoch" in payload
    assert "best_map50" in payload


def test_list_runs_prefers_worker_status_file(tmp_fovux_home: Path) -> None:
    """Run listing should not show stale SQLite status when the worker wrote a terminal state."""
    run_dir, _registry = _seed_run(tmp_fovux_home, run_id="run_failed")
    (run_dir / "status.json").write_text('{"status": "failed"}', encoding="utf-8")

    with TestClient(create_app()) as client:
        response = client.get("/runs", headers=_auth_headers(client))

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["id"] == "run_failed"
    assert payload[0]["status"] == "failed"


def test_search_runs_filters_query_tags_status_and_map50(tmp_fovux_home: Path) -> None:
    """Run search should combine text, tag, status, and minimum mAP filters."""
    paths = ensure_fovux_dirs(tmp_fovux_home)
    registry = RunRegistry(paths.runs_db)
    match_dir = paths.runs / "run_release_candidate"
    skip_dir = paths.runs / "run_cpu_smoke"
    match_dir.mkdir(parents=True)
    skip_dir.mkdir(parents=True)
    registry.create_run(
        run_id="run_release_candidate",
        run_path=match_dir,
        model="yolov8m.pt",
        dataset_path=tmp_fovux_home / "production-dataset",
        task="detect",
        epochs=50,
        tags=["production", "edge"],
        extra={"note": "needle"},
    )
    registry.update_status("run_release_candidate", "complete")
    registry.create_run(
        run_id="run_cpu_smoke",
        run_path=skip_dir,
        model="yolov8n.pt",
        dataset_path=tmp_fovux_home / "smoke-dataset",
        task="detect",
        epochs=5,
        tags=["smoke"],
    )
    registry.update_status("run_cpu_smoke", "failed")
    (match_dir / "results.csv").write_text(
        "epoch,metrics/mAP50(B)\n0,0.30\n1,0.74\n",
        encoding="utf-8",
    )
    (skip_dir / "results.csv").write_text(
        "epoch,metrics/mAP50(B)\n0,0.20\n",
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.post(
            "/runs/search",
            json={
                "query": "needle",
                "tags": ["edge"],
                "status": ["complete"],
                "min_map50": 0.70,
                "limit": 1,
            },
            headers=_auth_headers(client),
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["id"] for item in payload] == ["run_release_candidate"]
    assert payload[0]["best_map50"] == pytest.approx(0.74)
    assert payload[0]["tags"] == ["edge", "production"]


def test_get_run_returns_current_epoch_and_metrics(tmp_fovux_home: Path) -> None:
    """Single-run metadata should include the most recent epoch and mAP value."""
    run_dir, _registry = _seed_run(tmp_fovux_home, run_id="run_details")
    (run_dir / "results.csv").write_text(
        "epoch,metrics/mAP50(B)\n0,0.40\n1,0.62\n",
        encoding="utf-8",
    )

    with TestClient(create_app()) as client:
        response = client.get("/runs/run_details", headers=_auth_headers(client))

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "run_details"
    assert payload["current_epoch"] == 2
    assert payload["best_map50"] == pytest.approx(0.62)


def test_get_run_missing_returns_404(tmp_fovux_home: Path) -> None:
    """Unknown runs should surface a not-found response."""
    with TestClient(create_app()) as client:
        response = client.get("/runs/ghost", headers=_auth_headers(client))

    assert response.status_code == 404


def test_tool_proxy_unknown_tool_returns_policy_error(tmp_fovux_home: Path) -> None:
    """Unknown tool names should follow the HTTP tool policy denial path."""
    with TestClient(create_app()) as client:
        response = client.post("/tools/ghost_tool", json={}, headers=_auth_headers(client))

    assert response.status_code == 403
    payload = response.json()["detail"]
    assert payload["code"] == "FOVUX_HTTP_001"
    assert "not available" in payload["message"]


def test_tool_proxy_fovux_error_returns_400(tmp_fovux_home: Path) -> None:
    """Fovux errors should be serialized as HTTP 400 responses."""
    with (
        patch(
            "fovux.http.tool_proxy.invoke_tool",
            side_effect=FovuxDatasetNotFoundError("/missing/dataset"),
        ),
        TestClient(create_app()) as client,
    ):
        response = client.post("/tools/model_list", json={}, headers=_auth_headers(client))

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["code"].startswith("FOVUX_DATASET_")


def test_tool_proxy_validation_error_returns_422(tmp_fovux_home: Path) -> None:
    """Tool schema validation errors should be returned as client errors."""
    with TestClient(create_app()) as client:
        response = client.post(
            "/tools/train_start",
            json={"dataset_path": ".", "name": "../x", "confirm": True},
            headers=_auth_headers(client),
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "FOVUX_HTTP_002"


def test_train_start_has_stricter_rate_limit_than_readonly_tools(tmp_fovux_home: Path) -> None:
    """Training launch attempts should be rate-limited more aggressively than read-only tools."""
    with TestClient(create_app()) as client:
        headers = _auth_headers(client)
        responses = [
            client.post(
                "/tools/train_start",
                json={"dataset_path": "/missing", "confirm": True},
                headers=headers,
            )
            for _ in range(6)
        ]
        readonly = client.post("/tools/model_list", json={}, headers=headers)

    assert [response.status_code for response in responses[:5]] == [400, 400, 400, 400, 400]
    assert responses[5].status_code == 429
    assert readonly.status_code == 200


def test_tool_proxy_rejects_saturated_concurrency_limit(tmp_fovux_home: Path) -> None:
    """Saturated tool semaphores should reject immediately instead of waiting."""
    with TestClient(create_app()) as client:
        client.app.state.tool_semaphores["model_list"] = asyncio.Semaphore(0)
        response = client.post("/tools/model_list", json={}, headers=_auth_headers(client))

    assert response.status_code == 429
    assert response.json()["detail"] == "Tool concurrency limit exceeded."


def test_long_running_http_tools_require_confirmation() -> None:
    """Expensive HTTP-exposed tools should require trusted UI confirmation."""
    for tool_name in ("benchmark_latency", "eval_run", "infer_rtsp"):
        assert HTTP_TOOL_POLICIES[tool_name].category == "long_running"
        assert HTTP_TOOL_POLICIES[tool_name].requires_confirmation is True


def test_tool_proxy_returns_operation_for_timed_out_worker(
    tmp_fovux_home: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timed-out thread workers should become idempotent background operations."""
    worker_finished = threading.Event()
    calls = 0

    def invoke_tool(name: str, payload: dict[str, object]) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 1:
            time.sleep(0.15)
            worker_finished.set()
        return {"ok": True}

    monkeypatch.setitem(
        HTTP_TOOL_POLICIES,
        "model_list",
        HttpToolPolicy("read_only", 0.05, 1),
    )
    monkeypatch.setattr("fovux.http.tool_proxy.invoke_tool", invoke_tool)

    with TestClient(create_app()) as client:
        headers = _auth_headers(client)
        first = client.post("/tools/model_list", json={}, headers=headers)
        second = client.post("/tools/model_list", json={}, headers=headers)
        assert worker_finished.wait(timeout=1.0)
        deadline = time.time() + 1.0
        while True:
            third = client.post("/tools/model_list", json={}, headers=headers)
            if third.status_code not in {202, 429} or time.time() >= deadline:
                break
            time.sleep(0.01)

    assert first.status_code == 202
    assert first.json()["operation_id"] == "model_list-44136fa355b3678a"
    assert second.status_code == 202
    assert second.json()["operation_id"] == first.json()["operation_id"]
    assert third.status_code == 200


def test_tool_proxy_returns_background_operation_error(tmp_fovux_home: Path) -> None:
    """Failed background operation retries should expose the stored local error detail."""
    with TestClient(create_app()) as client:
        client.app.state.tool_operation_results["model_list:44136fa355b3678a"] = {
            "operation_id": "model_list-44136fa355b3678a",
            "status": "failed",
            "error_type": "RuntimeError",
            "error": "background failed",
            "finished_at": time.monotonic(),
        }
        response = client.post("/tools/model_list", json={}, headers=_auth_headers(client))

    assert response.status_code == 500
    assert response.json() == {
        "operation_id": "model_list-44136fa355b3678a",
        "status": "failed",
        "error_type": "RuntimeError",
        "error": "background failed",
    }


def test_timed_out_worker_exception_is_logged_before_semaphore_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Background worker failures after a timeout should remain observable."""
    events: list[tuple[str, dict[str, object]]] = []

    class Logger:
        def warning(self, event: str, **kwargs: object) -> None:
            events.append((event, kwargs))

        def error(self, event: str, **kwargs: object) -> None:
            events.append((event, kwargs))

    async def scenario() -> None:
        semaphore = asyncio.Semaphore(0)
        future: asyncio.Future[object] = asyncio.get_running_loop().create_future()
        future.set_exception(RuntimeError("worker failed"))
        callback = _release_semaphore_after_worker(semaphore)
        callback(future)
        await asyncio.wait_for(semaphore.acquire(), timeout=0.1)

    monkeypatch.setattr("fovux.http.routes.get_logger", lambda _name: Logger())

    asyncio.run(scenario())

    assert events == [
        (
            "http_tool_worker_failed_after_timeout",
            {"error_type": "RuntimeError", "error": "worker failed"},
        )
    ]


def test_timed_out_operation_callback_tracks_result_and_expiry() -> None:
    """Timed-out tool operations should keep one retrievable result for idempotent retry."""

    async def scenario() -> None:
        semaphore = asyncio.Semaphore(0)
        future: asyncio.Future[object] = asyncio.get_running_loop().create_future()
        operations: dict[str, asyncio.Future[object]] = {"model_list:abc": future}
        results: dict[str, dict[str, object]] = {}

        callback = _remember_timed_out_tool_worker(
            semaphore=semaphore,
            operations=operations,
            results=results,
            operation_key="model_list:abc",
            operation_id=_tool_operation_id("model_list", "abc"),
        )
        future.set_result({"ok": True})
        callback(future)
        await asyncio.wait_for(semaphore.acquire(), timeout=0.1)

        assert operations == {}
        fresh = _pop_fresh_tool_operation_result(results, "model_list:abc")
        assert fresh is not None
        assert fresh["operation_id"] == "model_list-abc"
        assert fresh["status"] == "succeeded"
        assert fresh["result"] == {"ok": True}
        fresh["finished_at"] = time.monotonic() - 301
        assert _pop_fresh_tool_operation_result(results, "model_list:abc") is None
        assert "model_list:abc" not in results

        results["model_list:bad"] = {"finished_at": "not-a-clock"}
        assert _pop_fresh_tool_operation_result(results, "model_list:bad") is None
        assert "model_list:bad" not in results

        failed_future: asyncio.Future[object] = asyncio.get_running_loop().create_future()
        operations["model_list:failed"] = failed_future
        failed_callback = _remember_timed_out_tool_worker(
            semaphore=semaphore,
            operations=operations,
            results=results,
            operation_key="model_list:failed",
            operation_id=_tool_operation_id("model_list", "failed"),
        )
        failed_future.set_exception(RuntimeError("background failed"))
        failed_callback(failed_future)
        await asyncio.wait_for(semaphore.acquire(), timeout=0.1)
        failed = _pop_fresh_tool_operation_result(results, "model_list:failed")
        assert failed is not None
        assert failed["status"] == "failed"
        assert failed["error_type"] == "RuntimeError"
        assert failed["error"] == "background failed"

        cancelled_future: asyncio.Future[object] = asyncio.get_running_loop().create_future()
        operations["model_list:cancelled"] = cancelled_future
        cancelled_callback = _remember_timed_out_tool_worker(
            semaphore=semaphore,
            operations=operations,
            results=results,
            operation_key="model_list:cancelled",
            operation_id=_tool_operation_id("model_list", "cancelled"),
        )
        cancelled_future.cancel()
        cancelled_callback(cancelled_future)
        await asyncio.wait_for(semaphore.acquire(), timeout=0.1)
        cancelled = _pop_fresh_tool_operation_result(results, "model_list:cancelled")
        assert cancelled is not None
        assert cancelled["status"] == "cancelled"

        results.clear()
        for index in range(130):
            results[f"old:{index}"] = {"finished_at": time.monotonic() - 301}
        results["fresh"] = {"finished_at": time.monotonic()}
        _prune_tool_operation_results(results)
        assert results == {"fresh": results["fresh"]}

    asyncio.run(scenario())


def test_resolve_run_dir_returns_registered_path(tmp_fovux_home: Path) -> None:
    """Internal run resolution should point to the registered run directory."""
    run_dir, _registry = _seed_run(tmp_fovux_home, run_id="run_dir")

    assert _resolve_run_dir("run_dir") == run_dir


def test_load_metrics_jsonl_skips_invalid_rows(tmp_path: Path) -> None:
    """JSONL metric loading should ignore blank and malformed lines."""
    run_dir = tmp_path / "run_jsonl"
    run_dir.mkdir()
    (run_dir / "metrics.jsonl").write_text(
        (
            '\n{"run_id": "run_jsonl", "epoch": 1, "metrics": {"metrics/mAP50(B)": 0.33}}\n'
            'not-json\n{"metrics": {"metrics/precision(B)": 0.71}}\n'
        ),
        encoding="utf-8",
    )

    payloads = _load_metrics_jsonl("run_jsonl", run_dir)

    assert payloads == [
        {
            "runId": "run_jsonl",
            "epoch": 1,
            "metrics": {"metrics/mAP50(B)": 0.33},
            "wall_time_s": 0.0,
            "eta_s": 0.0,
        },
    ]


def test_load_metric_payloads_falls_back_to_metrics_jsonl(tmp_path: Path) -> None:
    """When CSV metrics are absent, the SSE loader should fall back to metrics.jsonl."""
    run_dir = tmp_path / "run_metrics"
    run_dir.mkdir()
    (run_dir / "metrics.jsonl").write_text(
        '{"run_id": "run_metrics", "epoch": 2, "metrics": {"metrics/mAP50(B)": 0.48}}\n'
    )

    payloads = _load_metric_payloads("run_metrics", run_dir)

    assert payloads == [
        {
            "runId": "run_metrics",
            "epoch": 2,
            "metrics": {"metrics/mAP50(B)": 0.48},
            "wall_time_s": 0.0,
            "eta_s": 0.0,
        },
    ]


def test_metric_event_stream_emits_keepalive_when_idle(tmp_path: Path) -> None:
    """Idle metric streams should emit heartbeat comments to keep SSE clients alive."""
    run_dir = tmp_path / "run_keepalive"
    run_dir.mkdir()

    async def disconnected() -> bool:
        return False

    async def immediate_timeout(awaitable: object, timeout: float) -> object:
        del timeout
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise TimeoutError

    async def consume_stream() -> str:
        shutdown_event = asyncio.Event()
        stream = _metric_event_stream(
            run_id="run_keepalive",
            run_dir=run_dir,
            disconnect_check=disconnected,
            shutdown_event=shutdown_event,
        )
        with patch("fovux.http.routes.asyncio.wait_for", side_effect=immediate_timeout):
            retry = await anext(stream)
            assert retry == "retry: 5000\n\n"
            heartbeat = await anext(stream)
        shutdown_event.set()
        await stream.aclose()
        return heartbeat

    heartbeat = asyncio.run(consume_stream())
    assert heartbeat == ": keep-alive\n\n"


def test_metric_event_stream_stops_on_disconnect(tmp_path: Path) -> None:
    """Disconnected clients should stop the async metric stream cleanly."""
    run_dir = tmp_path / "run_disconnect"
    run_dir.mkdir()

    async def disconnected() -> bool:
        return True

    async def consume_stream() -> None:
        shutdown_event = asyncio.Event()
        stream = _metric_event_stream(
            run_id="run_disconnect",
            run_dir=run_dir,
            disconnect_check=disconnected,
            shutdown_event=shutdown_event,
        )
        retry = await anext(stream)
        assert retry == "retry: 5000\n\n"
        with pytest.raises(StopAsyncIteration):
            await anext(stream)

    asyncio.run(consume_stream())
