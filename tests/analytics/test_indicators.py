from __future__ import annotations

import csv
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


GOLDEN_CSV = Path(__file__).parent.parent / "golden" / "GPUS_20260814.csv"

# Mirrors collectors/market_data/tests/fixtures/GPUS_2026-08-14.csv (BT-01)
# exactly -- kept as a literal list here so this test has no dependency on
# a live database or on that fixture file's path.
GPUS_BARS = [
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


def _bars_up_to(as_of: datetime) -> list[dict]:
    return [b for b in GPUS_BARS if b["bar_start"] <= as_of]


def _load_golden_rows():
    with open(GOLDEN_CSV, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.mark.parametrize("row", _load_golden_rows())
def test_golden_dataset(row):
    as_of = datetime.strptime(row["as_of"], "%Y-%m-%d %H:%M:%S")
    bars = _bars_up_to(as_of)
    expected = float(row["expected"])

    if row["indicator"] == "vwap":
        actual = calculate_vwap_from_bars(bars)
    elif row["indicator"] == "rvol":
        timeframe_minutes = parse_timeframe_minutes(row["timeframe"])
        actual = calculate_rvol_from_bars(
            bars, timeframe_minutes, lookback=int(row["lookback"])
        )
    else:
        raise ValueError(f"Unknown golden indicator {row['indicator']!r}")

    assert actual == pytest.approx(expected)


def test_calculate_vwap_from_bars_empty_returns_none():
    assert calculate_vwap_from_bars([]) is None


def test_calculate_rvol_from_bars_insufficient_history_returns_none():
    assert calculate_rvol_from_bars(GPUS_BARS[:5], 5, lookback=5) is None


def test_parse_timeframe_minutes_rejects_unknown():
    with pytest.raises(ValueError):
        parse_timeframe_minutes("7m")


def _fake_context(bars):
    context = MagicMock()
    context.fetch_bars.return_value = bars
    return context


def test_calculate_vwap_delegates_to_injected_context():
    context = _fake_context(GPUS_BARS)

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
    context = _fake_context(GPUS_BARS)

    result = calculate_rvol(
        ticker="GPUS",
        as_of=datetime(2026, 8, 14, 9, 44, 0),
        timeframe="5m",
        lookback=2,
        context=context,
    )

    context.fetch_bars.assert_called_once_with(
        ticker="GPUS", trading_day=date(2026, 8, 14)
    )
    assert result == pytest.approx(1.08)
