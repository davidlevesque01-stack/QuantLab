from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock, patch

from analytics.replay.market_bar_source import MarketBarSource


ROWS = [
    ("GPUS", "Q", datetime(2026, 8, 14, 9, 30, 0), 2.00, 2.05, 1.98, 2.02, 10000),
    ("GPUS", "Q", datetime(2026, 8, 14, 9, 31, 0), 2.02, 2.04, 2.00, 2.03, 8000),
]


def _fake_connection(rows):
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False

    connection = MagicMock()
    connection.cursor.return_value = cursor
    connection.__enter__.return_value = connection
    connection.__exit__.return_value = False

    return connection, cursor


def test_fetch_bars_returns_canonical_shape():
    connection, cursor = _fake_connection(ROWS)

    with patch(
        "analytics.replay.market_bar_source.get_connection",
        return_value=connection,
    ):
        bars = MarketBarSource().fetch_bars(
            ticker="GPUS",
            trading_day=date(2026, 8, 14),
        )

    assert bars == [
        {
            "ticker": "GPUS",
            "market": "Q",
            "bar_start": datetime(2026, 8, 14, 9, 30, 0),
            "open": 2.00,
            "high": 2.05,
            "low": 1.98,
            "close": 2.02,
            "volume": 10000,
        },
        {
            "ticker": "GPUS",
            "market": "Q",
            "bar_start": datetime(2026, 8, 14, 9, 31, 0),
            "open": 2.02,
            "high": 2.04,
            "low": 2.00,
            "close": 2.03,
            "volume": 8000,
        },
    ]


def test_fetch_bars_without_as_of_does_not_add_predicate():
    connection, cursor = _fake_connection(ROWS)

    with patch(
        "analytics.replay.market_bar_source.get_connection",
        return_value=connection,
    ):
        MarketBarSource().fetch_bars(ticker="GPUS", trading_day=date(2026, 8, 14))

    query, params = cursor.execute.call_args[0]

    assert "bar_start <= %s" not in query
    assert params == ["GPUS", date(2026, 8, 14), date(2026, 8, 14)]


def test_fetch_bars_with_as_of_adds_point_in_time_predicate():
    connection, cursor = _fake_connection(ROWS)
    as_of = datetime(2026, 8, 14, 9, 30, 30)

    with patch(
        "analytics.replay.market_bar_source.get_connection",
        return_value=connection,
    ):
        MarketBarSource().fetch_bars(
            ticker="GPUS",
            trading_day=date(2026, 8, 14),
            as_of=as_of,
        )

    query, params = cursor.execute.call_args[0]

    assert "bar_start <= %s" in query
    assert params == ["GPUS", date(2026, 8, 14), date(2026, 8, 14), as_of]


def test_fetch_bars_empty_result():
    connection, cursor = _fake_connection([])

    with patch(
        "analytics.replay.market_bar_source.get_connection",
        return_value=connection,
    ):
        bars = MarketBarSource().fetch_bars(
            ticker="NOSUCHTICKER",
            trading_day=date(2026, 8, 14),
        )

    assert bars == []
