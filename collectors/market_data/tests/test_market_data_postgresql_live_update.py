from datetime import datetime

from shared.database import get_connection

from collectors.market_data.src.market_data_postgresql import (
    write_core_market_bars,
    write_market_bars,
)


# ============================================================
# QUANTLAB - MARKET_BAR_1M RAW+CORE LIVE UPDATE TEST
# ============================================================
#
# Goal:
#
#   1. First ingestion       -> INSERT
#   2. Identical re-ingestion -> no-op (ON CONFLICT DO NOTHING)
#   3. Final ROLLBACK        -> no test data persisted
#
# Uses a ticker reserved for QuantLab to avoid colliding with a real symbol.
# Requires QUANTLAB_DB_* and migration 018 applied -- confirm both with the
# user before running this test (see feedback_manual_db_steps memory).
#
# ============================================================


TEST_TICKER = "QLV10TEST"
TEST_SOURCE = "test_fixture"

BARS = [
    {
        "ticker": TEST_TICKER,
        "market": "Q",
        "bar_start": datetime(2099, 1, 2, 9, 30, 0),
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


def test_market_bar_1m_capture_is_idempotent():
    conn = get_connection()

    try:
        if _count_test_rows(conn, "raw.market_bar_1m") != 0:
            raise RuntimeError(
                "Test data already exists in raw.market_bar_1m. "
                "The previous test may not have been rolled back."
            )

        if _count_test_rows(conn, "core.market_bar_1m") != 0:
            raise RuntimeError(
                "Test data already exists in core.market_bar_1m. "
                "The previous test may not have been rolled back."
            )

        first_raw = write_market_bars(conn, BARS, TEST_SOURCE)
        first_core = write_core_market_bars(conn, BARS, TEST_SOURCE)

        assert first_raw == {"inserted": 1, "skipped": 0}
        assert first_core == {"inserted": 1, "skipped": 0}
        assert _count_test_rows(conn, "raw.market_bar_1m") == 1
        assert _count_test_rows(conn, "core.market_bar_1m") == 1

        second_raw = write_market_bars(conn, BARS, TEST_SOURCE)
        second_core = write_core_market_bars(conn, BARS, TEST_SOURCE)

        assert second_raw == {"inserted": 0, "skipped": 1}
        assert second_core == {"inserted": 0, "skipped": 1}
        assert _count_test_rows(conn, "raw.market_bar_1m") == 1
        assert _count_test_rows(conn, "core.market_bar_1m") == 1

    finally:
        conn.rollback()
        conn.close()
