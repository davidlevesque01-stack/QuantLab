"""Point-in-time guard for the Replay Engine (BT-03).

MarketContext(as_of=...) makes look-ahead bias structurally impossible, not
just discouraged by convention -- see docs/backtesting/BACKTESTING_COMPONENT.md,
principle 1 ("No knowledge of the future"). A request for
information_timestamp > as_of is technically rejected (raises
LookAheadViolation), not silently filtered.

assert_visible() is deliberately generic (any information_timestamp, not
just market bars) -- the same doc principle states MarketContext is meant to
eventually guard every historical data type a model consumes (bars, HALTs,
SEC filings, warrants), not just market bars. This ticket only wires bars,
but the guard itself is reusable as-is by future data types.

fetch_bars() delegates to MarketBarSource (BT-17, analytics/replay/
market_bar_source.py), which already filters at the SQL level
(bar_start <= as_of) -- but that's a filtering primitive, not a guard.
fetch_bars() re-validates every row it gets back through assert_visible()
as defense in depth, so MarketContext structurally rejects a violation even
if the underlying source has a bug (or is a test double that misbehaves),
per docs/backtesting/BACKTESTING_COMPONENT.md's validation plan item 3:
"Prove MarketContext(as_of=...) technically rejects any read past the
simulated clock (the single most important test in this component)."
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


class LookAheadViolation(Exception):
    """Raised when a caller (or an underlying data source) would expose
    information from after the simulated clock's current time.
    """


class MarketContext:
    """Point-in-time-scoped read boundary. Constructed fresh per simulated
    tick (see SimulatedClock) with market_bar_source injected, matching
    AnalysisService's core_source=None pattern (analytics/nasdaq_halts/
    analysis_service.py).
    """

    def __init__(self, as_of: datetime, market_bar_source=None):
        if as_of.tzinfo is not None:
            raise ValueError("MarketContext expects a naive as_of (no tzinfo)")

        self.as_of = as_of
        self.market_bar_source = market_bar_source

    def assert_visible(self, information_timestamp: datetime) -> None:
        if information_timestamp.tzinfo is not None:
            raise ValueError(
                "MarketContext expects a naive information_timestamp (no tzinfo)"
            )

        if information_timestamp > self.as_of:
            raise LookAheadViolation(
                f"information_timestamp {information_timestamp} is after "
                f"as_of {self.as_of}"
            )

    def fetch_bars(self, *, ticker: str, trading_day: date) -> list[dict[str, Any]]:
        if self.market_bar_source is None:
            raise RuntimeError(
                "No market_bar_source configured. Supply one to MarketContext."
            )

        bars = self.market_bar_source.fetch_bars(
            ticker=ticker,
            trading_day=trading_day,
            as_of=self.as_of,
        )

        for bar in bars:
            self.assert_visible(bar["bar_start"])

        return bars
