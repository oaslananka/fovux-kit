"""Thread-scoped stdout and stderr redirection for background HTTP workers."""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TextIO

_THREAD_LOCAL = threading.local()


class ThreadLocalStream:
    """Delegate writes to a thread-scoped stream when one is active."""

    def __init__(self, original_stream: Any) -> None:  # noqa: ANN401
        """Initialize the stream wrapper."""
        self.original_stream = original_stream

    def write(self, data: str) -> int:
        """Write to the active thread stream or the original stream."""
        stream = getattr(_THREAD_LOCAL, "stream", None)
        if stream is not None:
            return stream.write(data)  # type: ignore[no-any-return]
        return self.original_stream.write(data)  # type: ignore[no-any-return]

    def flush(self) -> None:
        """Flush the active thread stream or the original stream."""
        stream = getattr(_THREAD_LOCAL, "stream", None)
        if stream is not None:
            stream.flush()
        else:
            self.original_stream.flush()

    def __getattr__(self, name: str) -> Any:  # noqa: ANN401
        """Delegate missing attributes to the original stream."""
        return getattr(self.original_stream, name)


def install_thread_local_streams() -> None:
    """Install idempotent stdout/stderr wrappers."""
    if not isinstance(sys.stdout, ThreadLocalStream):
        sys.stdout = ThreadLocalStream(sys.stdout)
    if not isinstance(sys.stderr, ThreadLocalStream):
        sys.stderr = ThreadLocalStream(sys.stderr)


@contextmanager
def redirect_thread_output(stream: TextIO) -> Iterator[None]:
    """Redirect output for the current thread for the context lifetime."""
    install_thread_local_streams()
    previous = getattr(_THREAD_LOCAL, "stream", None)
    _THREAD_LOCAL.stream = stream
    try:
        yield
    finally:
        if previous is None:
            try:
                delattr(_THREAD_LOCAL, "stream")
            except AttributeError:
                pass
        else:
            _THREAD_LOCAL.stream = previous
