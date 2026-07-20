"""Launch mutmut with third-party import hooks isolated from its test runner."""

from __future__ import annotations

import multiprocessing


def _preload_multiprocessing() -> None:
    """Create one harmless pool before mutation tests import optional dependencies."""
    context = multiprocessing.get_context("fork")
    with context.Pool(processes=1) as pool:
        result = pool.apply(int, ("1",))
    if result != 1:
        raise RuntimeError("multiprocessing preload failed")


def _disable_optional_dependency_import_hook() -> None:
    """Prevent py-key-value-aio from registering a global beartype Claw hook."""
    import beartype.claw

    def no_op_hook(*_args: object, **_kwargs: object) -> None:
        return None

    beartype.claw.beartype_this_package = no_op_hook


def main() -> None:
    """Import and invoke mutmut after its Python runtime is isolated."""
    _preload_multiprocessing()
    _disable_optional_dependency_import_hook()

    import pytest  # noqa: F401 -- preload before mutation tests import optional packages
    from mutmut.__main__ import cli

    cli()


if __name__ == "__main__":
    main()
