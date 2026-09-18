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
# test_market_bar_1m_null_market_capture_is_idempotent additionally requires
# migration 020 applied (the partial unique indexes covering market IS NULL,
# BT-11) -- confirm with the user before running it.
#
# ============================================================


TEST_TICKER = "QLV10TEST"
TEST_TICKER_NULL_MARKET = "QLV10TSTN"
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

NULL_MARKET_BARS = [
    {
        "ticker": TEST_TICKER_NULL_MARKET,
        "market": None,
        "bar_start": datetime(2099, 1, 2, 9, 30, 0),
        "open": 1.0,
        "high": 1.05,
        "low": 0.98,
        "close": 1.02,
        "volume": 1000,
        "market_scope": "CONSOLIDATED_US",
        "session": "REGULAR",
        "transaction_count": 12,
        "source_provider": "MASSIVE",
        "source_dataset": "us_stocks_sip/minute_aggs_v1",
        "dataset_version": "minute_aggs_v1",
        "ingestion_run_id": "test-run",
    }
]


def _count_test_rows(conn, table, ticker=TEST_TICKER):
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM {table} WHERE ticker = %s;",
            (ticker,),
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


def test_market_bar_1m_null_market_capture_is_idempotent():
    conn = get_connection()

    try:
        if _count_test_rows(conn, "raw.market_bar_1m", TEST_TICKER_NULL_MARKET) != 0:
            raise RuntimeError(
                "Test data already exists in raw.market_bar_1m. "
                "The previous test may not have been rolled back."
            )

        if _count_test_rows(conn, "core.market_bar_1m", TEST_TICKER_NULL_MARKET) != 0:
            raise RuntimeError(
                "Test data already exists in core.market_bar_1m. "
                "The previous test may not have been rolled back."
            )

        first_raw = write_market_bars(conn, NULL_MARKET_BARS, TEST_SOURCE)
        first_core = write_core_market_bars(conn, NULL_MARKET_BARS, TEST_SOURCE)

        assert first_raw == {"inserted": 1, "skipped": 0}
        assert first_core == {"inserted": 1, "skipped": 0}
        assert _count_test_rows(conn, "raw.market_bar_1m", TEST_TICKER_NULL_MARKET) == 1
        assert _count_test_rows(conn, "core.market_bar_1m", TEST_TICKER_NULL_MARKET) == 1

        second_raw = write_market_bars(conn, NULL_MARKET_BARS, TEST_SOURCE)
        second_core = write_core_market_bars(conn, NULL_MARKET_BARS, TEST_SOURCE)

        assert second_raw == {"inserted": 0, "skipped": 1}
        assert second_core == {"inserted": 0, "skipped": 1}
        assert _count_test_rows(conn, "raw.market_bar_1m", TEST_TICKER_NULL_MARKET) == 1
        assert _count_test_rows(conn, "core.market_bar_1m", TEST_TICKER_NULL_MARKET) == 1

    finally:
        conn.rollback()
        conn.close()
