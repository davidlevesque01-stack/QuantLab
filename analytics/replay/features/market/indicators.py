"""Minimal Feature Engine (BT-04): VWAP and RVOL.

Point-in-time discipline: the pure `*_from_bars` functions never fetch data
and never know about the simulated clock -- the no-look-ahead guarantee
comes entirely from the caller only ever passing bars already known as of
`as_of`. The `calculate_*` wrappers follow the architecture's uniform
`calculate(ticker, as_of, timeframe)` signature (see
docs/backtesting/BACKTESTING_COMPONENT.md) and are the only functions here
that touch PostgreSQL -- via `MarketContext` (BT-03), never
`MarketBarSource` directly, so every feature gets BT-03's defense-in-depth
look-ahead guard for free, not just raw SQL filtering. Callers can inject a
fake `MarketContext` in tests without needing a live database.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from analytics.replay.aggregation import DAILY_MINUTES, aggregate_bars
from analytics.replay.market_bar_source import MarketBarSource
from analytics.replay.market_context import MarketContext


_TIMEFRAME_MINUTES = {
    "1m": 1,
    "2m": 2,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "1d": DAILY_MINUTES,
    "daily": DAILY_MINUTES,
}


def parse_timeframe_minutes(timeframe: str) -> int:
    try:
        return _TIMEFRAME_MINUTES[timeframe]
    except KeyError:
        raise ValueError(
            f"Unknown timeframe {timeframe!r}; expected one of "
            f"{sorted(_TIMEFRAME_MINUTES)}"
        ) from None


def calculate_vwap_from_bars(bars: list[dict[str, Any]]) -> float | None:
    """Volume Weighted Average Price over `bars`.

    VWAP = sum(typical_price_i * volume_i) / sum(volume_i), where
    typical_price = (high + low + close) / 3 -- the standard formula.
    `timeframe` has no effect on the result (VWAP over the same time range
    is invariant to how the underlying minutes are chunked), which is why
    only `calculate_vwap` (not this function) accepts it -- purely to keep
    the same call shape as every other feature.

    Returns None for an empty bar list or zero total volume (can't divide).
    """

    total_volume = sum(bar["volume"] for bar in bars)

    if total_volume == 0:
        return None

    weighted_sum = sum(
        ((bar["high"] + bar["low"] + bar["close"]) / 3) * bar["volume"]
        for bar in bars
    )

    return weighted_sum / total_volume


def calculate_rvol_from_bars(
    bars: list[dict[str, Any]],
    timeframe_minutes: int,
    *,
    lookback: int = 5,
) -> float | None:
    """Relative Volume: the most recent `timeframe_minutes` bucket's volume
    divided by the average volume of the `lookback` buckets preceding it.

    Deliberate MVP simplification: this compares a bucket to its own recent
    local history, not to a same-time-of-day average across prior trading
    days (the conventional RVOL definition) -- that needs a multi-day
    historical baseline this component does not have yet with only a single
    fixture day to validate against. Revisit once enough real Massive
    history is ingested (BT-11) to compute a genuine trailing-day baseline.

    Returns None if there are fewer than `lookback + 1` buckets (not enough
    history to compare against), or the preceding buckets' average volume
    is zero.
    """

    buckets = aggregate_bars(bars, timeframe_minutes)

    if len(buckets) < lookback + 1:
        return None

    current = buckets[-1]
    preceding = buckets[-(lookback + 1) : -1]

    average_volume = sum(b.volume for b in preceding) / len(preceding)

    if average_volume == 0:
        return None

    return current.volume / average_volume


def _default_context(as_of: datetime) -> MarketContext:
    return MarketContext(as_of=as_of, market_bar_source=MarketBarSource())


def calculate_vwap(
    *,
    ticker: str,
    as_of: datetime,
    timeframe: str,
    context: MarketContext | None = None,
) -> float | None:
    context = context or _default_context(as_of)

    bars = context.fetch_bars(ticker=ticker, trading_day=as_of.date())

    return calculate_vwap_from_bars(bars)


def calculate_rvol(
    *,
    ticker: str,
    as_of: datetime,
    timeframe: str,
    lookback: int = 5,
    context: MarketContext | None = None,
) -> float | None:
    context = context or _default_context(as_of)

    bars = context.fetch_bars(ticker=ticker, trading_day=as_of.date())
    timeframe_minutes = parse_timeframe_minutes(timeframe)

    return calculate_rvol_from_bars(bars, timeframe_minutes, lookback=lookback)
