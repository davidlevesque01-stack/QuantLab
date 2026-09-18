from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from analytics.replay.features.market.indicators import (
    calculate_rvol,
    calculate_rvol_from_bars,
    calculate_vwap,
    calculate_vwap_from_bars,
    parse_timeframe_minutes,
)


GOLDEN_CSV = Path(__file__).parent.parent / "golden" / "GPUS_20260917.csv"
GOLDEN_BARS_CSV = (
    Path(__file__).parent.parent / "golden" / "GPUS_1m_bars_2026-09-09_to_2026-09-17.csv"
)

# Real Massive-sourced GPUS 1-minute bars for 2026-09-09..2026-09-17 (BT-11
# backfill), independently re-aggregated with pandas (not this module's own
# aggregate_bars) to produce GPUS_20260917.csv's expected values -- see
# tests/golden/GPUS_20260917.csv. Loaded once per test session; this module
# has no dependency on a live database.
def _load_golden_bars() -> dict[date, list[dict]]:
    by_day: dict[date, list[dict]] = defaultdict(list)

    with open(GOLDEN_BARS_CSV, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            bar_start = datetime.strptime(row["bar_start"], "%Y-%m-%d %H:%M:%S")
            by_day[bar_start.date()].append(
                {
                    "bar_start": bar_start,
                    "open": float(row["open"]),
                    "high": float(row["high"]),
                    "low": float(row["low"]),
                    "close": float(row["close"]),
                    "volume": int(row["volume"]),
                }
            )

    return dict(by_day)


GOLDEN_BARS_BY_DAY = _load_golden_bars()

# Matches GPUS_20260917.csv's rvol rows (lookback=5 trading days before
# 2026-09-17): 09-12/09-13 are a weekend, so this is Thu/Wed/Mon/Fri/Tue.
GOLDEN_HISTORICAL_DAYS = [
    date(2026, 9, 16),
    date(2026, 9, 15),
    date(2026, 9, 14),
    date(2026, 9, 11),
    date(2026, 9, 10),
]

# Small synthetic single-day fixture, kept only for structural/edge-case and
# delegation tests below that don't need to be realistic -- real multi-day
# market behavior is covered by the golden dataset test above.
SAMPLE_BARS = [
    {"bar_start": datetime(2026, 8, 14, 9, 30, 0), "open": 2.00, "high": 2.05, "low": 1.98, "close": 2.02, "volume": 10000},
    {"bar_start": datetime(2026, 8, 14, 9, 31, 0), "open": 2.02, "high": 2.04, "low": 2.00, "close": 2.03, "volume": 8000},
    {"bar_start": datetime(2026, 8, 14, 9, 32, 0), "open": 2.03, "high": 2.10, "low": 2.01, "close": 2.08, "volume": 12000},
    {"bar_start": datetime(2026, 8, 14, 9, 33, 0), "open": 2.08, "high": 2.09, "low": 2.05, "close": 2.06, "volume": 9000},
    {"bar_start": datetime(2026, 8, 14, 9, 34, 0), "open": 2.06, "high": 2.07, "low": 2.00, "close": 2.01, "volume": 7000},
    {"bar_start": datetime(2026, 8, 14, 9, 35, 0), "open": 2.01, "high": 2.06, "low": 2.01, "close": 2.05, "volume": 6000},
    {"bar_start": datetime(2026, 8, 14, 9, 36, 0), "open": 2.05, "high": 2.12, "low": 2.04, "close": 2.11, "volume": 15000},
    {"bar_start": datetime(2026, 8, 14, 9, 37, 0), "open": 2.11, "high": 2.15, "low": 2.09, "close": 2.10, "volume": 14000},
    {"bar_start": datetime(2026, 8, 14, 9, 38, 0), "open": 2.10, "high": 2.11, "low": 2.03, "close": 2.04, "volume": 11000},
    {"bar_start": datetime(2026, 8, 14, 9, 39, 0), "open": 2.04, "high": 2.08, "low": 2.02, "close": 2.07, "volume": 8000},
    {"bar_start": datetime(2026, 8, 14, 9, 40, 0), "open": 2.07, "high": 2.09, "low": 2.05, "close": 2.06, "volume": 5000},
    {"bar_start": datetime(2026, 8, 14, 9, 41, 0), "open": 2.06, "high": 2.06, "low": 1.95, "close": 1.97, "volume": 20000},
    {"bar_start": datetime(2026, 8, 14, 9, 42, 0), "open": 1.97, "high": 2.00, "low": 1.95, "close": 1.99, "volume": 13000},
    {"bar_start": datetime(2026, 8, 14, 9, 43, 0), "open": 1.99, "high": 2.03, "low": 1.98, "close": 2.02, "volume": 9000},
    {"bar_start": datetime(2026, 8, 14, 9, 44, 0), "open": 2.02, "high": 2.04, "low": 2.00, "close": 2.03, "volume": 7000},
]


def _bars_up_to(day: date, as_of: datetime) -> list[dict]:
    return [b for b in GOLDEN_BARS_BY_DAY[day] if b["bar_start"] <= as_of]


def _load_golden_rows():
    with open(GOLDEN_CSV, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize("row", _load_golden_rows())
def test_golden_dataset(row):
    as_of = datetime.strptime(row["as_of"], "%Y-%m-%d %H:%M:%S")
    bars = _bars_up_to(as_of.date(), as_of)
    expected = float(row["expected"])

    if row["indicator"] == "vwap":
        actual = calculate_vwap_from_bars(bars)
    elif row["indicator"] == "rvol":
        timeframe_minutes = parse_timeframe_minutes(row["timeframe"])
        historical_bars = [GOLDEN_BARS_BY_DAY[d] for d in GOLDEN_HISTORICAL_DAYS[: int(row["lookback"])]]
        actual = calculate_rvol_from_bars(
            bars, timeframe_minutes, historical_bars=historical_bars
        )
    else:
        raise ValueError(f"Unknown golden indicator {row['indicator']!r}")

    assert actual == pytest.approx(expected)


def test_calculate_vwap_from_bars_empty_returns_none():
    assert calculate_vwap_from_bars([]) is None


def test_calculate_rvol_from_bars_empty_bars_returns_none():
    assert calculate_rvol_from_bars([], 5, historical_bars=[SAMPLE_BARS]) is None


def test_calculate_rvol_from_bars_no_historical_days_returns_none():
    assert calculate_rvol_from_bars(SAMPLE_BARS, 5, historical_bars=[]) is None


def test_calculate_rvol_from_bars_matches_same_time_of_day_bucket():
    # Current bucket (09:40-09:45) volume: 5000+20000+13000+9000+7000 = 54000.
    # Each "historical day" here is the same SAMPLE_BARS day, so its
    # 09:40-09:45 bucket is identically 54000 -- RVOL of exactly 1.0 proves
    # the bucket-matching (not just averaging) is doing the work.
    result = calculate_rvol_from_bars(
        SAMPLE_BARS, 5, historical_bars=[SAMPLE_BARS, SAMPLE_BARS]
    )
    assert result == pytest.approx(1.0)


def test_parse_timeframe_minutes_rejects_unknown():
    with pytest.raises(ValueError):
        parse_timeframe_minutes("7m")


def _fake_context(bars):
    context = MagicMock()
    context.fetch_bars.return_value = bars
    return context


def test_calculate_vwap_delegates_to_injected_context():
    context = _fake_context(SAMPLE_BARS)

    result = calculate_vwap(
        ticker="GPUS",
        as_of=datetime(2026, 8, 14, 9, 44, 0),
        timeframe="5m",
        context=context,
    )

    context.fetch_bars.assert_called_once_with(
        ticker="GPUS", trading_day=date(2026, 8, 14)
    )
    assert result == pytest.approx(2.041450216450216)


def test_calculate_rvol_delegates_to_injected_context():
    # Every call (today + each historical trading day) returns the same
    # single-day fixture, so this isolates the *wiring* (call count/args)
    # from domain correctness (covered by the golden dataset test): a
    # bucket compared against copies of itself must come out to RVOL 1.0.
    context = _fake_context(SAMPLE_BARS)

    result = calculate_rvol(
        ticker="GPUS",
        as_of=datetime(2026, 8, 14, 9, 44, 0),
        timeframe="5m",
        lookback=2,
        context=context,
    )

    assert context.fetch_bars.call_count == 3
    context.fetch_bars.assert_any_call(ticker="GPUS", trading_day=date(2026, 8, 14))
    context.fetch_bars.assert_any_call(ticker="GPUS", trading_day=date(2026, 8, 13))
    context.fetch_bars.assert_any_call(ticker="GPUS", trading_day=date(2026, 8, 12))
    assert result == pytest.approx(1.0)
