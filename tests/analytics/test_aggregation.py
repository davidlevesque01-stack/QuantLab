from __future__ import annotations

from datetime import datetime

from analytics.replay.aggregation import DAILY_MINUTES, aggregate_bars


def _bar(minute_offset, open_, high, low, close, volume, day=(2026, 8, 14), hour=9, base_minute=30):
    year, month, dom = day
    total_minutes = base_minute + minute_offset
    hh = hour + total_minutes // 60
    mm = total_minutes % 60
    return {
        "ticker": "GPUS",
        "market": "Q",
        "bar_start": datetime(year, month, dom, hh, mm, 0),
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


FIVE_MIN_BARS = [
    _bar(0, 2.00, 2.05, 1.98, 2.02, 10000),  # 09:30
    _bar(1, 2.02, 2.04, 2.00, 2.03, 8000),  # 09:31
    _bar(2, 2.03, 2.10, 2.01, 2.08, 12000),  # 09:32
    _bar(3, 2.08, 2.09, 2.05, 2.06, 9000),  # 09:33
    _bar(4, 2.06, 2.07, 2.00, 2.01, 7000),  # 09:34
]


def test_aggregate_1m_to_5m_basic():
    result = aggregate_bars(FIVE_MIN_BARS, 5)

    assert len(result) == 1
    bucket = result[0]
    assert bucket.bucket_start == datetime(2026, 8, 14, 9, 30, 0)
    assert bucket.bucket_end == datetime(2026, 8, 14, 9, 35, 0)
    assert bucket.open == 2.00
    assert bucket.high == 2.10
    assert bucket.low == 1.98
    assert bucket.close == 2.01
    assert bucket.volume == 46000
    assert bucket.is_closed is True


def test_aggregate_1m_to_2m_splits_into_multiple_buckets():
    result = aggregate_bars(FIVE_MIN_BARS, 2)

    assert [b.bucket_start for b in result] == [
        datetime(2026, 8, 14, 9, 30, 0),
        datetime(2026, 8, 14, 9, 32, 0),
        datetime(2026, 8, 14, 9, 34, 0),
    ]

    first = result[0]
    assert first.open == 2.00
    assert first.high == 2.05
    assert first.low == 1.98
    assert first.close == 2.03
    assert first.volume == 18000

    last = result[2]
    assert last.open == 2.06
    assert last.high == 2.07
    assert last.low == 2.00
    assert last.close == 2.01
    assert last.volume == 7000


def test_aggregate_1m_to_15m_and_30m_and_1h():
    # Anchored at 09:00 (a clean hour boundary) rather than the 09:30 default
    # so a full 60-minute run produces exactly one hourly bucket -- 09:30
    # itself is not hour-aligned (bucketing is midnight-anchored, and 9:30
    # is 570 minutes past midnight, not a multiple of 60).
    bars = [
        _bar(i, 2.00 + i * 0.01, 2.05 + i * 0.01, 1.98, 2.02, 1000, hour=9, base_minute=0)
        for i in range(60)
    ]

    fifteen = aggregate_bars(bars, 15)
    assert len(fifteen) == 4
    assert fifteen[0].volume == 15000

    thirty = aggregate_bars(bars, 30)
    assert len(thirty) == 2
    assert thirty[0].volume == 30000

    hourly = aggregate_bars(bars, 60)
    assert len(hourly) == 1
    assert hourly[0].volume == 60000
    assert hourly[0].open == bars[0]["open"]
    assert hourly[0].close == bars[-1]["close"]


def test_aggregate_1m_to_daily_groups_by_calendar_day():
    bars = [
        _bar(0, 2.00, 2.05, 1.98, 2.02, 10000, day=(2026, 8, 14)),
        _bar(1, 2.02, 2.04, 2.00, 2.03, 8000, day=(2026, 8, 14)),
        _bar(0, 3.00, 3.05, 2.98, 3.02, 5000, day=(2026, 8, 17)),
    ]

    result = aggregate_bars(bars, DAILY_MINUTES)

    assert len(result) == 2
    assert result[0].bucket_start == datetime(2026, 8, 14, 0, 0, 0)
    assert result[0].volume == 18000
    assert result[1].bucket_start == datetime(2026, 8, 17, 0, 0, 0)
    assert result[1].volume == 5000


def test_in_progress_bucket_is_flagged_and_reflects_only_available_minutes():
    partial = FIVE_MIN_BARS[:3]  # 09:30, 09:31, 09:32 only -- bucket not over yet

    result = aggregate_bars(partial, 5, as_of=datetime(2026, 8, 14, 9, 32, 30))

    assert len(result) == 1
    bucket = result[0]
    assert bucket.is_closed is False
    # Must reflect only the 3 minutes actually passed in -- never the
    # eventual close/high/low that the missing 09:33/09:34 bars would add.
    assert bucket.high == 2.10
    assert bucket.low == 1.98
    assert bucket.close == 2.08
    assert bucket.volume == 30000


def test_bucket_is_closed_once_as_of_reaches_bucket_end():
    result = aggregate_bars(FIVE_MIN_BARS, 5, as_of=datetime(2026, 8, 14, 9, 35, 0))

    assert result[0].is_closed is True


def test_as_of_none_treats_every_bucket_as_closed():
    result = aggregate_bars(FIVE_MIN_BARS[:3], 5, as_of=None)

    assert result[0].is_closed is True


def test_empty_input_returns_empty_list():
    assert aggregate_bars([], 5) == []
