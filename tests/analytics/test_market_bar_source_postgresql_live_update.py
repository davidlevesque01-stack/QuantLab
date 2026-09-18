from datetime import date, datetime

from shared.database import get_connection

from analytics.replay.market_bar_source import MarketBarSource
from collectors.market_data.src.market_data_postgresql import (
    write_core_market_bars,
    write_market_bars,
)


# ============================================================
# QUANTLAB - MARKETBARSOURCE LIVE READ TEST
# ============================================================
#
# Goal:
#
#   1. Insert a synthetic bar (committed -- MarketBarSource opens its own
#      connection, so an uncommitted row on a different connection would be
#      invisible to it under READ COMMITTED).
#   2. Read it back through MarketBarSource -- validates the real SQL
#      against the real schema, not just the mocked unit tests.
#   3. Validate the as_of point-in-time filter actually filters.
#   4. Explicit DELETE cleanup (not ROLLBACK -- the insert was committed on
#      purpose so a second connection could see it).
#
# Uses a ticker reserved for QuantLab to avoid colliding with a real symbol.
# Requires QUANTLAB_DB_* and migrations 018/019 applied -- confirm with the
# user before running this test (see feedback_manual_db_steps memory).
#
# ============================================================


TEST_TICKER = "QLV17TEST"
TEST_SOURCE = "test_fixture"
BAR_START = datetime(2099, 1, 2, 9, 30, 0)

BARS = [
    {
        "ticker": TEST_TICKER,
        "market": "Q",
        "bar_start": BAR_START,
        "open": 1.0,
        "high": 1.05,
        "low": 0.98,
        "close": 1.02,
        "volume": 1000,
    }
]


def _count_test_rows(conn, table):
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM {table} WHERE ticker = %s;",
            (TEST_TICKER,),
        )
        return cur.fetchone()[0]


def _delete_test_rows(conn):
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM core.market_bar_1m WHERE ticker = %s;", (TEST_TICKER,)
        )
        cur.execute("DELETE FROM raw.market_bar_1m WHERE ticker = %s;", (TEST_TICKER,))
    conn.commit()


def test_market_bar_source_reads_real_committed_row():
    conn = get_connection()

    try:
        if _count_test_rows(conn, "raw.market_bar_1m") != 0:
            raise RuntimeError(
                "Test data already exists in raw.market_bar_1m. "
                "A previous run of this test may not have cleaned up."
            )
        if _count_test_rows(conn, "core.market_bar_1m") != 0:
            raise RuntimeError(
                "Test data already exists in core.market_bar_1m. "
                "A previous run of this test may not have cleaned up."
            )

        write_market_bars(conn, BARS, TEST_SOURCE)
        write_core_market_bars(conn, BARS, TEST_SOURCE)
        conn.commit()

        source = MarketBarSource()

        bars = source.fetch_bars(ticker=TEST_TICKER, trading_day=date(2099, 1, 2))

        assert bars == [
            {
                "ticker": TEST_TICKER,
                "market": "Q",
                "bar_start": BAR_START,
                "open": 1.0,
                "high": 1.05,
                "low": 0.98,
                "close": 1.02,
                "volume": 1000,
            }
        ]

        at_bar_time = source.fetch_bars(
            ticker=TEST_TICKER,
            trading_day=date(2099, 1, 2),
            as_of=BAR_START,
        )
        assert len(at_bar_time) == 1

        before_bar_time = source.fetch_bars(
            ticker=TEST_TICKER,
            trading_day=date(2099, 1, 2),
            as_of=datetime(2099, 1, 2, 9, 29, 0),
        )
        assert before_bar_time == []

    finally:
        _delete_test_rows(conn)
        conn.close()
