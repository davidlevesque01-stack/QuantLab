"""Aggregation Engine (BT-02): deterministic 1-minute bar aggregation.

Turns 1-minute bars (from the Historical Data API, BT-17's
`MarketBarSource`) into 2m/5m/15m/30m/1h/daily bars. Only 1-minute OHLCV is
ever persisted (BT-01/BT-11) -- every larger timeframe is computed here, on
demand, never sourced from a provider's own aggregation.

Point-in-time note: this module does not know about `as_of` and never
fetches data itself -- it only aggregates whatever 1-minute bars the caller
passes in. The no-look-ahead guarantee comes entirely from the caller only
ever passing bars already known as of the simulated clock (BT-17's
`MarketBarSource(as_of=...)`, BT-03's `MarketContext`). Passed a truncated
list, an in-progress bucket's OHLCV reflects only those bars -- it is never
back-filled from bars the caller did not include.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any


DAILY_MINUTES = 1440


@dataclass(frozen=True)
class AggregatedBar:
    bucket_start: datetime
    bucket_end: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    is_closed: bool


def _bucket_start(bar_start: datetime, timeframe_minutes: int) -> datetime:
    midnight = datetime.combine(bar_start.date(), time.min)
    minutes_since_midnight = int((bar_start - midnight).total_seconds() // 60)
    bucket_index = minutes_since_midnight // timeframe_minutes
    return midnight + timedelta(minutes=bucket_index * timeframe_minutes)


def aggregate_bars(
    bars: list[dict[str, Any]],
    timeframe_minutes: int,
    *,
    as_of: datetime | None = None,
) -> list[AggregatedBar]:
    """Aggregate 1-minute bars into `timeframe_minutes`-minute buckets.

    OPEN = first open in the bucket, HIGH = max high, LOW = min low,
    CLOSE = last close, VOLUME = sum of volume -- 100% deterministic, no
    floating-point tolerance. `bars` must already be ordered by
    `bar_start` (as `MarketBarSource`/`QuantLabAdapter` both guarantee) and
    belong to a single ticker/day.

    A bucket is Closed (`is_closed=True`) once its end boundary is at or
    before `as_of`; it is In-Progress (`is_closed=False`) otherwise. If
    `as_of` is None, every bucket is treated as closed (e.g. a full
    end-of-day batch aggregation, where there is no simulated clock to be
    ahead of).

    `timeframe_minutes=1440` (`DAILY_MINUTES`) produces one bucket per
    calendar day -- the same midnight-anchored bucketing handles "daily"
    without a special case.
    """

    if not bars:
        return []

    buckets: dict[datetime, list[dict[str, Any]]] = {}

    for bar in bars:
        start = _bucket_start(bar["bar_start"], timeframe_minutes)
        buckets.setdefault(start, []).append(bar)

    result = []

    for start in sorted(buckets):
        members = buckets[start]
        end = start + timedelta(minutes=timeframe_minutes)

        is_closed = as_of is None or as_of >= end

        result.append(
            AggregatedBar(
                bucket_start=start,
                bucket_end=end,
                open=members[0]["open"],
                high=max(b["high"] for b in members),
                low=min(b["low"] for b in members),
                close=members[-1]["close"],
                volume=sum(b["volume"] for b in members),
                is_closed=is_closed,
            )
        )

    return result
