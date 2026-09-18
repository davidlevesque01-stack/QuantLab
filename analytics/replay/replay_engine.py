"""Replay Engine (BT-05): orchestrates clock -> context -> raw bars.

Single ReplayEngine class drives the full loop for one ticker/day and
exposes state at each simulated minute -- designed so Interactive Replay
(BT-06a) and Batch Replay (BT-09) reuse it unchanged, per
docs/backtesting/BACKTESTING_COMPONENT.md principle 3 ("One Replay Engine,
two modes"). Reads market bars through the Historical Data API
(MarketBarSource, BT-17), never through a Source Adapter directly.

No aggregation/feature step in this pass -- raw 1-minute bars only, in the
same canonical shape aggregate_bars() (BT-02, analytics/replay/
aggregation.py) already consumes, so BT-02/BT-04 slot in later without
changing ReplayEngine's public interface. No PySide6 dependency: PLAY/PAUSE
timing is BT-06a's job (a UI timer calling advance() repeatedly), this class
only provides the stepping primitives.

Each step reconstructs a fresh MarketContext(as_of=..., market_bar_source=...)
and queries MarketBarSource -- deliberately no in-memory caching/pre-fetch
layer in this pass (see BT-05's plan notes): batch replay of thousands of
ticker/day scenarios (BT-09) may need to optimize this later, but that's
unmeasured and out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterator

from shared.calendar.trading_calendar import get_session_bounds, is_trading_day

from analytics.replay.market_bar_source import MarketBarSource
from analytics.replay.market_context import MarketContext


@dataclass(frozen=True)
class ReplayState:
    current_time: datetime
    ticker: str
    trading_day: date
    bars: list[dict[str, Any]]


class ReplayEngine:
    """Drives a SimulatedClock-equivalent loop for one ticker/day, exposing
    a ReplayState (point-in-time-filtered raw bars) at each simulated
    minute.
    """

    def __init__(
        self,
        *,
        ticker: str,
        trading_day: date,
        market_bar_source=None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ):
        if not is_trading_day(trading_day):
            raise ValueError(f"{trading_day} is not a Nasdaq trading day")

        bounds = get_session_bounds(trading_day)

        self.ticker = ticker
        self.trading_day = trading_day
        self._market_bar_source = market_bar_source or MarketBarSource()

        self._current_time = start_time or datetime.combine(
            trading_day, bounds.pre_market_open
        )
        self._end_time = end_time or datetime.combine(
            trading_day, bounds.after_hours_close
        )

    @property
    def current_time(self) -> datetime:
        return self._current_time

    @property
    def state(self) -> ReplayState:
        context = MarketContext(
            as_of=self._current_time,
            market_bar_source=self._market_bar_source,
        )
        bars = context.fetch_bars(ticker=self.ticker, trading_day=self.trading_day)

        return ReplayState(
            current_time=self._current_time,
            ticker=self.ticker,
            trading_day=self.trading_day,
            bars=bars,
        )

    def advance(self, minutes: int = 1) -> ReplayState:
        self._set_current_time(self._current_time + timedelta(minutes=minutes))
        return self.state

    def rewind(self, minutes: int = 1) -> ReplayState:
        self._set_current_time(self._current_time - timedelta(minutes=minutes))
        return self.state

    def seek(self, new_time: datetime) -> ReplayState:
        self._set_current_time(new_time)
        return self.state

    def run(self) -> Iterator[ReplayState]:
        """Steps minute-by-minute from the current position through
        end_time (inclusive), yielding state at every simulated minute.
        This is the loop Batch Replay (BT-09) consumes directly -- no
        parallel reimplementation of the stepping logic.
        """

        yield self.state

        while self._current_time < self._end_time:
            yield self.advance()

    def _set_current_time(self, new_time: datetime) -> None:
        if new_time.tzinfo is not None:
            raise ValueError("ReplayEngine expects a naive datetime (no tzinfo)")

        self._current_time = new_time
