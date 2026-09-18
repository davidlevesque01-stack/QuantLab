"""Simulated clock for the Replay Engine (BT-03).

Holds the "current simulated time" that MarketContext is constructed from
at each tick. Deliberately minimal -- no calendar/session validation here,
that's shared/calendar/trading_calendar.py's job, not the clock's. See
docs/backtesting/BACKTESTING_GITHUB_BACKLOG.md#bt-03.
"""

from __future__ import annotations

from datetime import datetime, timedelta


class SimulatedClock:
    """Mutable holder of the current simulated time (naive, Nasdaq-local
    wall-clock, matching the project's timestamp convention).
    """

    def __init__(self, start_time: datetime):
        if start_time.tzinfo is not None:
            raise ValueError("SimulatedClock expects a naive datetime (no tzinfo)")

        self._current_time = start_time

    @property
    def current_time(self) -> datetime:
        return self._current_time

    def advance(self, minutes: int = 1) -> datetime:
        self._current_time += timedelta(minutes=minutes)
        return self._current_time

    def rewind(self, minutes: int = 1) -> datetime:
        self._current_time -= timedelta(minutes=minutes)
        return self._current_time

    def set_time(self, new_time: datetime) -> None:
        if new_time.tzinfo is not None:
            raise ValueError("SimulatedClock expects a naive datetime (no tzinfo)")

        self._current_time = new_time
