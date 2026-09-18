from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from analytics.replay.simulated_clock import SimulatedClock


def test_construction_sets_current_time():
    start = datetime(2026, 8, 14, 9, 30, 0)
    clock = SimulatedClock(start)

    assert clock.current_time == start


def test_construction_rejects_aware_datetime():
    aware = datetime(2026, 8, 14, 9, 30, 0, tzinfo=ZoneInfo("UTC"))

    with pytest.raises(ValueError):
        SimulatedClock(aware)


def test_advance_defaults_to_one_minute():
    clock = SimulatedClock(datetime(2026, 8, 14, 9, 30, 0))

    result = clock.advance()

    assert result == datetime(2026, 8, 14, 9, 31, 0)
    assert clock.current_time == datetime(2026, 8, 14, 9, 31, 0)


def test_advance_accepts_explicit_minutes():
    clock = SimulatedClock(datetime(2026, 8, 14, 9, 30, 0))

    clock.advance(minutes=5)

    assert clock.current_time == datetime(2026, 8, 14, 9, 35, 0)


def test_rewind_defaults_to_one_minute():
    clock = SimulatedClock(datetime(2026, 8, 14, 9, 30, 0))

    result = clock.rewind()

    assert result == datetime(2026, 8, 14, 9, 29, 0)
    assert clock.current_time == datetime(2026, 8, 14, 9, 29, 0)


def test_rewind_accepts_explicit_minutes():
    clock = SimulatedClock(datetime(2026, 8, 14, 9, 30, 0))

    clock.rewind(minutes=10)

    assert clock.current_time == datetime(2026, 8, 14, 9, 20, 0)


def test_set_time_jumps_to_arbitrary_timeline_position():
    clock = SimulatedClock(datetime(2026, 8, 14, 9, 30, 0))

    clock.set_time(datetime(2026, 8, 14, 15, 45, 0))

    assert clock.current_time == datetime(2026, 8, 14, 15, 45, 0)


def test_set_time_rejects_aware_datetime():
    clock = SimulatedClock(datetime(2026, 8, 14, 9, 30, 0))
    aware = datetime(2026, 8, 14, 10, 0, 0, tzinfo=ZoneInfo("UTC"))

    with pytest.raises(ValueError):
        clock.set_time(aware)
