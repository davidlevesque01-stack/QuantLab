from datetime import date, datetime
from pathlib import Path

import pytest

from collectors.market_data.src.csv_adapter import CSVAdapter


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_fetch_bars_reads_fixture_in_order():
    adapter = CSVAdapter(FIXTURES_DIR)

    bars = adapter.fetch_bars("GPUS", date(2026, 8, 14))

    assert len(bars) == 15
    assert bars[0]["bar_start"] == datetime(2026, 8, 14, 9, 30, 0)
    assert bars[-1]["bar_start"] == datetime(2026, 8, 14, 9, 44, 0)
    assert [bar["bar_start"] for bar in bars] == sorted(
        bar["bar_start"] for bar in bars
    )


def test_fetch_bars_returns_canonical_shape():
    adapter = CSVAdapter(FIXTURES_DIR)

    bar = adapter.fetch_bars("GPUS", date(2026, 8, 14))[0]

    assert bar == {
        "ticker": "GPUS",
        "market": "Q",
        "bar_start": datetime(2026, 8, 14, 9, 30, 0),
        "open": 2.00,
        "high": 2.05,
        "low": 1.98,
        "close": 2.02,
        "volume": 10000,
    }


def test_fetch_bars_missing_fixture_raises():
    adapter = CSVAdapter(FIXTURES_DIR)

    with pytest.raises(FileNotFoundError):
        adapter.fetch_bars("NOSUCHTICKER", date(2026, 8, 14))
