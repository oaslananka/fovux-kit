"""Focused tests for registry datetime storage helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fovux.core.run_registry.models import _deserialize_datetime, _serialize_datetime


def test_datetime_helpers_normalize_aware_values_to_naive_utc() -> None:
    aware = datetime(2026, 1, 1, 3, 0, tzinfo=timezone(timedelta(hours=3)))

    assert _serialize_datetime(aware) == "2026-01-01T00:00:00.000000"
    assert _deserialize_datetime(aware) == datetime(2026, 1, 1)
