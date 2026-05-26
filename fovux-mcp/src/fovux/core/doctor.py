"""Shared environment diagnostics for the CLI and MCP tool surface."""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

import httpx

from fovux.core.paths import FovuxPaths, ensure_fovux_dirs, get_fovux_home
from fovux.schemas.diagnostics import (
    FovuxDoctorOutput,
    FovuxHomeHealth,
    GpuHealth,
    HttpHealth,
    PackageHealth,
    SystemSnapshot,
)


def collect_doctor_report() -> FovuxDoctorOutput:
    """Collect a shared Fovux environment report for CLI and MCP usage."""
    paths = ensure_fovux_dirs(get_fovux_home())
    warnings: list[str] = []
    errors: list[str] = []

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    gpu = _detect_gpu()
    ultralytics = _import_health("ultralytics")
    onnxruntime = _onnxruntime_health()
    onnx = _import_health("onnx")
    fastmcp = _import_health("fastmcp")
    http = _probe_http_transport(paths)
    home = _inspect_fovux_home(paths)
    system = _system_snapshot(paths)
    requirements = _requirements(gpu, home)
    license_notices = [
        "Ultralytics is distributed under AGPL-3.0 terms; review NOTICE before redistribution."
    ]

    if not gpu.available:
        warnings.append(
            "No hardware accelerator was detected; training and inference will use CPU."
        )
    if ultralytics.status != "ok":
        errors.append("Ultralytics is unavailable, so training/evaluation tools cannot run.")
    if onnxruntime.status != "ok":
        warnings.append("onnxruntime is unavailable; ONNX benchmarking and parity checks may fail.")
    if not http.reachable:
        warnings.append("The local HTTP transport is offline; Studio live views require it.")
    if home.disk_low:
        warnings.append("FOVUX_HOME has less than 5 GB free; long training runs may fail.")

    return FovuxDoctorOutput(
        python=python_version,
        gpu=gpu,
        ultralytics=ultralytics,
        onnxruntime=onnxruntime,
        onnx=onnx,
        fastmcp=fastmcp,
        http=http,
        fovux_home=home,
        system=system,
        license_notices=license_notices,
        requirements=requirements,
        warnings=warnings,
        errors=errors,
    )


def _import_health(module_name: str) -> PackageHealth:
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        return PackageHealth(status="missing", version=None, detail=str(exc))
    version = getattr(module, "__version__", None)
    return PackageHealth(status="ok", version=str(version) if version is not None else "unknown")


def _onnxruntime_health() -> PackageHealth:
    try:
        module = importlib.import_module("onnxruntime")
    except ImportError as exc:
        return PackageHealth(status="missing", version=None, detail=str(exc))
    providers = []
    get_available_providers = getattr(module, "get_available_providers", None)
    if callable(get_available_providers):
        providers = [str(item) for item in get_available_providers()]
    detail = ", ".join(providers) if providers else "No providers reported"
    version = getattr(module, "__version__", None)
    return PackageHealth(
        status="ok",
        version=str(version) if version is not None else "unknown",
        detail=detail,
    )


def _detect_gpu() -> GpuHealth:
    try:
        torch = importlib.import_module("torch")
    except ImportError:
        return GpuHealth(available=False, accelerator="cpu", detail="torch is not installed")

    cuda = getattr(torch, "cuda", None)
    if cuda is not None and callable(getattr(cuda, "is_available", None)) and cuda.is_available():
        device_name = (
            cuda.get_device_name(0) if callable(getattr(cuda, "get_device_name", None)) else None
        )
        memory_free_gb, memory_total_gb = _torch_cuda_memory_gb(cuda)
        return GpuHealth(
            available=True,
            accelerator="cuda",
            device=str(device_name) if device_name is not None else None,
            detail="CUDA is available",
            cuda_version=str(getattr(torch.version, "cuda", "")) or None,
            cudnn_version=_torch_cudnn_version(torch),
            memory_free_gb=memory_free_gb,
            memory_total_gb=memory_total_gb,
        )

    backends = getattr(torch, "backends", None)
    mps_backend = getattr(backends, "mps", None) if backends is not None else None
    if (
        mps_backend is not None
        and callable(getattr(mps_backend, "is_available", None))
        and mps_backend.is_available()
    ):
        return GpuHealth(
            available=True,
            accelerator="mps",
            device="Apple Silicon GPU",
            detail="Metal Performance Shaders is available",
        )

    return GpuHealth(
        available=False,
        accelerator="cpu",
        detail="No CUDA or MPS accelerator detected",
    )


def _probe_http_transport(paths: FovuxPaths) -> HttpHealth:
    socket_path = paths.home / "fovux.sock"
    base_url = "http://127.0.0.1:7823/health"
    try:
        response = httpx.get(base_url, timeout=1.5)
        if response.is_success:
            return HttpHealth(
                reachable=True,
                base_url=base_url,
                socket_path=socket_path,
                socket_exists=socket_path.exists(),
                detail="TCP health check succeeded",
            )
        return HttpHealth(
            reachable=False,
            base_url=base_url,
            socket_path=socket_path,
            socket_exists=socket_path.exists(),
            detail=f"Health endpoint returned HTTP {response.status_code}",
        )
    except Exception as exc:
        detail = "Unix socket present" if socket_path.exists() else str(exc)
        return HttpHealth(
            reachable=False,
            base_url=base_url,
            socket_path=socket_path,
            socket_exists=socket_path.exists(),
            detail=detail,
        )


def _inspect_fovux_home(paths: FovuxPaths) -> FovuxHomeHealth:
    usage = shutil.disk_usage(paths.home)
    run_count = len(list(paths.runs.glob("*"))) if paths.runs.exists() else 0
    model_count = (
        len([path for path in paths.models.glob("*") if path.is_file()])
        if paths.models.exists()
        else 0
    )
    writable = _is_writable(paths.home)
    return FovuxHomeHealth(
        path=paths.home,
        writable=writable,
        disk_free_gb=round(usage.free / (1024**3), 2),
        disk_low=usage.free < 5 * 1024**3,
        run_count=run_count,
        model_count=model_count,
    )


def _system_snapshot(paths: FovuxPaths) -> SystemSnapshot:
    active_runs = 0
    try:
        from fovux.core.runs import get_registry

        registry = get_registry(paths.runs_db)
        active_runs = len(registry.list_runs(status="running", limit=10_000))
    except Exception:
        active_runs = 0

    try:
        psutil = importlib.import_module("psutil")
        memory = psutil.virtual_memory()
        return SystemSnapshot(
            active_runs=active_runs,
            cpu_percent=float(psutil.cpu_percent(interval=0.0)),
            ram_percent=float(memory.percent),
            ram_total_gb=round(float(memory.total) / (1024**3), 2),
        )
    except ImportError:
        return SystemSnapshot(active_runs=active_runs)


def _requirements(gpu: GpuHealth, home: FovuxHomeHealth) -> dict[str, bool]:
    return {
        "python_supported": (3, 11) <= sys.version_info[:2] < (3, 14),
        "fovux_home_writable": home.writable,
        "disk_minimum_5gb": not home.disk_low,
        "accelerator_available": gpu.available,
    }


def _torch_cudnn_version(torch: object) -> str | None:
    backends = getattr(torch, "backends", None)
    cudnn = getattr(backends, "cudnn", None) if backends is not None else None
    version = getattr(cudnn, "version", None) if cudnn is not None else None
    if callable(version):
        value = version()
        return str(value) if value is not None else None
    return None


def _torch_cuda_memory_gb(cuda: object) -> tuple[float | None, float | None]:
    mem_get_info = getattr(cuda, "mem_get_info", None)
    if not callable(mem_get_info):
        return None, None
    try:
        free_bytes, total_bytes = mem_get_info()
    except Exception:
        return None, None
    return round(float(free_bytes) / (1024**3), 2), round(float(total_bytes) / (1024**3), 2)


def _is_writable(path: Path) -> bool:
    try:
        probe = path / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False
