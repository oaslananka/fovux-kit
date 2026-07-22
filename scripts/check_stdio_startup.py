"""Repeat raw MCP initialize against the production stdio entry point and enforce its budget."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2025-11-25"
PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "fovux-mcp"


async def _stderr_tail(process: asyncio.subprocess.Process) -> str:
    if process.stderr is None:
        return ""
    try:
        data = await asyncio.wait_for(process.stderr.read(8192), timeout=0.2)
    except TimeoutError:
        return ""
    return data.decode("utf-8", errors="replace")[-4000:]


async def _stop_process(process: asyncio.subprocess.Process) -> None:
    if process.stdin is not None and not process.stdin.is_closing():
        process.stdin.close()
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
        return
    except TimeoutError:
        pass
    if sys.platform != "win32":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    else:
        process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
    except TimeoutError:
        process.kill()
        await process.wait()


async def _run_round(round_number: int, budget_seconds: float) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"fovux-stdio-{round_number}-") as home:
        env = os.environ.copy()
        env["FOVUX_HOME"] = home
        env["FASTMCP_CHECK_FOR_UPDATES"] = "off"
        env["FOVUX_STARTUP_DIAGNOSTICS"] = "1"
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "fovux.stdio",
            cwd=PACKAGE_ROOT,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=sys.platform != "win32",
        )
        started_at = time.monotonic()
        try:
            assert process.stdin is not None
            assert process.stdout is not None
            request = {
                "jsonrpc": "2.0",
                "id": round_number,
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "fovux-startup-check", "version": "1"},
                },
            }
            process.stdin.write(
                json.dumps(request, separators=(",", ":")).encode() + b"\n"
            )
            await process.stdin.drain()
            try:
                line = await asyncio.wait_for(
                    process.stdout.readline(), timeout=budget_seconds
                )
            except TimeoutError as exc:
                stderr = await _stderr_tail(process)
                raise RuntimeError(
                    f"round {round_number} exceeded {budget_seconds:.1f}s; "
                    f"returncode={process.returncode}; stderr_tail={stderr!r}"
                ) from exc
            elapsed = time.monotonic() - started_at
            if not line:
                raise RuntimeError(
                    f"round {round_number} exited before initialize; "
                    f"returncode={process.returncode}; stderr_tail={await _stderr_tail(process)!r}"
                )
            response = json.loads(line)
            if response.get("id") != round_number:
                raise RuntimeError(
                    f"round {round_number} returned unexpected response: {response}"
                )
            result = response.get("result", {})
            if result.get("protocolVersion") != PROTOCOL_VERSION:
                raise RuntimeError(
                    f"round {round_number} negotiated unexpected protocol: {result}"
                )
            return {"round": round_number, "elapsed_seconds": round(elapsed, 3)}
        finally:
            await _stop_process(process)


async def _run(rounds: int, budget_seconds: float) -> list[dict[str, Any]]:
    results = []
    for round_number in range(1, rounds + 1):
        result = await _run_round(round_number, budget_seconds)
        print(json.dumps(result, sort_keys=True), flush=True)
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--budget-seconds", type=float, default=25.0)
    args = parser.parse_args()
    if args.rounds < 1:
        parser.error("--rounds must be at least 1")
    if args.budget_seconds <= 0:
        parser.error("--budget-seconds must be positive")
    results = asyncio.run(_run(args.rounds, args.budget_seconds))
    worst = max(float(item["elapsed_seconds"]) for item in results)
    print(
        f"Stdio startup reliability passed: rounds={args.rounds}, "
        f"budget={args.budget_seconds:.1f}s, worst={worst:.3f}s."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
