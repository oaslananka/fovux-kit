"""infer_rtsp — run live inference over an RTSP stream."""

from __future__ import annotations

import importlib
import queue
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, cast

from fovux.core.checkpoints import resolve_checkpoint
from fovux.core.errors import FovuxRtspConnectionError
from fovux.core.tooling import tool_event
from fovux.core.ultralytics_adapter import load_yolo_model
from fovux.core.validation import ensure_writable_output
from fovux.schemas.inference import InferRtspInput, InferRtspOutput
from fovux.server import mcp
from fovux.tools.infer_image import _parse_detections


@mcp.tool()
def infer_rtsp(
    checkpoint: str,
    rtsp_url: str,
    duration_seconds: int = 30,
    imgsz: int = 640,
    conf: float = 0.25,
    save_video: bool = False,
    output_path: str | None = None,
    frame_skip: int = 0,
    device: str = "auto",
    max_reconnect_attempts: int = 10,
) -> dict[str, Any]:
    """Run RTSP inference with frame skipping, reconnection, and optional video save."""
    inp = InferRtspInput(
        checkpoint=checkpoint,
        rtsp_url=rtsp_url,
        duration_seconds=duration_seconds,
        imgsz=imgsz,
        conf=conf,
        save_video=save_video,
        output_path=Path(output_path) if output_path else None,
        frame_skip=frame_skip,
        device=device,
        max_reconnect_attempts=max_reconnect_attempts,
    )
    with tool_event("infer_rtsp", checkpoint=checkpoint, rtsp_url=rtsp_url):
        return _run_infer_rtsp(inp).model_dump(mode="json")


def _run_infer_rtsp(inp: InferRtspInput) -> InferRtspOutput:
    checkpoint = resolve_checkpoint(inp.checkpoint)
    initial_capture = _open_rtsp_capture(inp.rtsp_url, raise_on_failure=True)
    try:
        model = load_yolo_model(checkpoint)
    except Exception:
        initial_capture.release()
        raise

    frame_queue: queue.Queue[object] = queue.Queue(maxsize=1)
    stop_event = threading.Event()
    capture_state = _CaptureState()
    capture_thread = threading.Thread(
        target=_capture_frames,
        args=(
            inp.rtsp_url,
            initial_capture,
            frame_queue,
            stop_event,
            capture_state,
            inp.max_reconnect_attempts,
        ),
        daemon=True,
    )
    capture_thread.start()

    writer: Any | None = None
    output_path = inp.output_path
    output_fps = 15.0
    counts: Counter[str] = Counter()
    frames_processed = 0
    frames_skipped = 0
    detection_count = 0
    frame_index = 0

    start = time.perf_counter()
    deadline = start + inp.duration_seconds

    try:
        while time.perf_counter() < deadline:
            try:
                frame = frame_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            frame_index += 1
            if inp.frame_skip and frame_index % (inp.frame_skip + 1) != 1:
                frames_skipped += 1
                continue

            result, rendered_frame = _infer_rtsp_frame(model, frame, inp)
            detections = _parse_detections(result)
            for detection in detections:
                counts[detection.class_name] += 1
            detection_count += len(detections)
            frames_processed += 1

            if inp.save_video:
                if writer is None:
                    output_path = ensure_writable_output(cast(Path, output_path))
                    output_fps = capture_state.fps or 15.0
                    writer = _open_video_writer(
                        output_path,
                        rendered_frame if rendered_frame is not None else frame,
                        output_fps,
                    )
                writer.write(rendered_frame if rendered_frame is not None else frame)
    finally:
        stop_event.set()
        capture_thread.join(timeout=2.0)
        if writer is not None:
            writer.release()

    duration_actual = max(time.perf_counter() - start, 1e-9)
    return InferRtspOutput(
        frames_processed=frames_processed,
        frames_skipped=frames_skipped,
        dropped_frames=capture_state.dropped_frames,
        avg_fps=frames_processed / duration_actual,
        detection_count=detection_count,
        detections_by_class=dict(counts),
        connection_status=capture_state.connection_status,
        reconnect_attempts=capture_state.reconnect_attempts,
        output_fps=output_fps,
        duration_actual_seconds=duration_actual,
        output_path=output_path if inp.save_video else None,
    )


class _CaptureState:
    def __init__(self) -> None:
        self.dropped_frames = 0
        self.reconnect_attempts = 0
        self.connection_status = "connected"
        self.fps = 15.0


def _capture_frames(
    rtsp_url: str,
    initial_capture: object,
    frame_queue: queue.Queue[object],
    stop_event: threading.Event,
    state: _CaptureState,
    max_reconnect_attempts: int,
) -> None:
    backoff = 0.25
    capture = cast(Any, initial_capture)
    try:
        while not stop_event.is_set():
            ok, frame = capture.read()
            if not ok:
                state.dropped_frames += 1
                state.reconnect_attempts += 1
                if state.reconnect_attempts >= max_reconnect_attempts:
                    state.connection_status = "disconnected"
                    break
                state.connection_status = "reconnecting"
                capture.release()
                time.sleep(backoff)
                backoff = min(backoff * 2, 5.0)
                try:
                    capture = _open_rtsp_capture(rtsp_url, raise_on_failure=False)
                except Exception:
                    state.connection_status = "disconnected"
                    break
                if not capture.isOpened():
                    state.connection_status = "disconnected"
                    continue
                state.connection_status = "reconnected"
                state.fps = _capture_fps(capture)
                continue

            backoff = 0.25
            state.connection_status = "connected"
            state.fps = _capture_fps(capture)
            try:
                frame_queue.put_nowait(frame)
            except queue.Full:
                try:
                    frame_queue.get_nowait()
                except queue.Empty:
                    pass
                state.dropped_frames += 1
                frame_queue.put_nowait(frame)
    finally:
        capture.release()


def _open_rtsp_capture(rtsp_url: str, *, raise_on_failure: bool) -> Any:  # noqa: ANN401
    cv2: Any = importlib.import_module("cv2")
    capture = cv2.VideoCapture(rtsp_url, getattr(cv2, "CAP_FFMPEG", 0))
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    if raise_on_failure and not capture.isOpened():
        raise FovuxRtspConnectionError(rtsp_url)
    return capture


def _capture_fps(capture: object) -> float:
    capture_obj = cast(Any, capture)
    if not hasattr(capture_obj, "get"):
        return 15.0
    cv2: Any = importlib.import_module("cv2")
    fps = float(capture_obj.get(cv2.CAP_PROP_FPS) or 0.0)
    return fps if fps > 0 else 15.0


def _infer_rtsp_frame(
    model: object,
    frame: object,
    inp: InferRtspInput,
) -> tuple[object, object | None]:
    predictor = cast(Any, model)
    results = predictor.predict(
        source=frame,
        imgsz=inp.imgsz,
        conf=inp.conf,
        device=inp.device,
        verbose=False,
    )
    result = results[0]
    rendered = result.plot() if hasattr(result, "plot") else None
    return result, rendered


def _open_video_writer(target: Path, sample_frame: Any, fps: float) -> Any:  # noqa: ANN401
    cv2: Any = importlib.import_module("cv2")
    target.parent.mkdir(parents=True, exist_ok=True)
    height, width = sample_frame.shape[:2]
    codecs = ("avc1", "mp4v")
    for codec in codecs:
        writer = cv2.VideoWriter(
            str(target),
            cv2.VideoWriter_fourcc(*codec),
            fps,
            (width, height),
        )
        if writer.isOpened():
            return writer
        writer.release()
    return cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
