"""Security tests — LLM input fuzzing for tool inputs.

Uses Hypothesis to generate adversarial inputs and validates that
the tool registry handles them safely (raises validation errors
rather than crashing or leaking information).
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fovux.core.tool_registry import _TOOL_SPECS, resolve_tool

# All registered tool names
TOOL_NAMES = sorted(_TOOL_SPECS.keys())


# Strategy for adversarial string inputs
adversarial_strings = st.one_of(
    st.text(min_size=0, max_size=10_000),  # Normal text including large
    st.just(""),
    st.just("../../etc/passwd"),
    st.just("/dev/null"),
    st.just("C:\\Windows\\System32\\cmd.exe"),
    st.just("\x00\x01\x02\x03"),  # Null bytes
    st.just("{{template_injection}}"),
    st.just("${env:SECRET}"),
    st.just("'; DROP TABLE runs; --"),
    st.just("\n\r\t"),
    st.just("a" * 100_000),
)


@pytest.mark.parametrize("tool_name", TOOL_NAMES)
@settings(max_examples=20, deadline=30_000)
@given(fuzz_value=adversarial_strings)
def test_tool_rejects_adversarial_input(tool_name: str, fuzz_value: str) -> None:
    """Every tool must either reject or handle adversarial inputs gracefully."""
    try:
        func = resolve_tool(tool_name)
        # Call with a single adversarial kwarg — we expect a validation error
        # or a meaningful error, not an unhandled crash
        func(dataset_path=fuzz_value)
    except (TypeError, ValueError, KeyError, FileNotFoundError, OSError, ImportError):
        pass  # Expected rejection
    except Exception as exc:
        # Allow Fovux-specific errors
        if "Fovux" in type(exc).__name__ or "fovux" in type(exc).__name__.lower():
            pass
        elif "pydantic" in type(exc).__module__.lower():
            pass  # Pydantic validation error
        else:
            raise AssertionError(
                f"Tool {tool_name} raised unexpected {type(exc).__name__}: {exc}"
            ) from exc
