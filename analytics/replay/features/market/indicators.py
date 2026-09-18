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

from datetime import date, datetime, timedelta
from typing import Any

from analytics.replay.aggregation import DAILY_MINUTES, aggregate_bars
from analytics.replay.market_bar_source import MarketBarSource
from analytics.replay.market_context import MarketContext
from shared.calendar.trading_calendar import is_trading_day


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


def _preceding_trading_days(day: date, count: int) -> list[date]:
    days: list[date] = []
    cursor = day - timedelta(days=1)

    while len(days) < count:
        if is_trading_day(cursor):
            days.append(cursor)
        cursor -= timedelta(days=1)

    return days


def calculate_rvol_from_bars(
    bars: list[dict[str, Any]],
    timeframe_minutes: int,
    *,
    historical_bars: list[list[dict[str, Any]]],
) -> float | None:
    """Relative Volume: the current `timeframe_minutes` bucket's volume
    divided by the average volume of the same time-of-day bucket across
    `historical_bars` -- the conventional RVOL definition (today's 09:30-
    09:35 volume vs. the average 09:30-09:35 volume of the preceding N
    trading days), not a same-day local comparison.

    `historical_bars` is one full day of 1-minute bars per preceding
    trading day (each day's bars, unfiltered -- an entire past trading day
    is always fully visible under the point-in-time guard, see
    MarketContext.fetch_bars). A historical day missing a bucket at the
    matching time-of-day (e.g. a partial trading day) is simply skipped
    rather than treated as zero volume.

    The current bucket may still be in progress (fewer minutes than a full
    bucket) if `bars` only extends to `as_of` mid-bucket -- this compares
    that partial volume to the *full* historical buckets, which is a known
    MVP limitation (no time-of-day-adjusted partial-bucket baseline yet).

    Returns None if `bars` is empty (no current bucket), if none of
    `historical_bars`' days have a bucket at the matching time-of-day, or
    if the resulting average baseline volume is zero.
    """

    current_buckets = aggregate_bars(bars, timeframe_minutes)

    if not current_buckets:
        return None

    current = current_buckets[-1]
    target_time = current.bucket_start.time()

    matching_volumes = []

    for day_bars in historical_bars:
        for bucket in aggregate_bars(day_bars, timeframe_minutes):
            if bucket.bucket_start.time() == target_time:
                matching_volumes.append(bucket.volume)
                break

    if not matching_volumes:
        return None

    average_volume = sum(matching_volumes) / len(matching_volumes)

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

    historical_bars = [
        context.fetch_bars(ticker=ticker, trading_day=day)
        for day in _preceding_trading_days(as_of.date(), lookback)
    ]

    return calculate_rvol_from_bars(
        bars, timeframe_minutes, historical_bars=historical_bars
    )
