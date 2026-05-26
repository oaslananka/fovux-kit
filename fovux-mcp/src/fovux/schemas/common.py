"""Shared Pydantic schema fragments."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, Field

from fovux.core.validation import RUN_ID_PATTERN, validate_run_id

RunId = Annotated[
    str,
    Field(pattern=RUN_ID_PATTERN, min_length=1, max_length=64),
    AfterValidator(validate_run_id),
]
