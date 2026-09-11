from datetime import datetime, timezone

from shared.database import get_connection

from collectors.warrants.src.warrants_postgresql import (
    read_sec_ticker_cik_resolutions,
    write_sec_ticker_cik_resolution,
)


# ============================================================
# QUANTLAB - SEC TICKER->CIK RESOLUTION RAW LIVE UPDATE TEST
# ============================================================
#
# Objectif :
#
#   1. Première ingestion    -> INSERT
#   2. Réingestion identique -> no-op (ON CONFLICT DO NOTHING)
#   3. ROLLBACK final        -> aucune donnée de test persistée
#
# Utilise volontairement un ticker réservé à QuantLab pour éviter toute
# collision avec un ticker réel.
#
# ============================================================


TEST_TICKER = "QLV08TEST"

RETRIEVED_AT = datetime(2099, 1, 2, 10, 0, 0, tzinfo=timezone.utc)

RESOLUTION = {
    "ticker": TEST_TICKER,
    "cik": "9999999995",
    "method": "name_search",
    "issuer_name_used": "QuantLab Test Issuer, Inc.",
    "matched_name": "QuantLab Test Issuer, Inc.",
}


def _count_test_rows(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM raw.sec_ticker_cik_resolution WHERE ticker = %s;",
            (TEST_TICKER,),
        )
        return cur.fetchone()[0]


def test_sec_ticker_cik_resolution_capture_is_idempotent():
    conn = get_connection()

    try:
        existing = _count_test_rows(conn)

        if existing != 0:
            raise RuntimeError(
                "Test data already exists in PostgreSQL. "
                "The previous test may not have been rolled back."
            )

        first_pass = write_sec_ticker_cik_resolution(
            conn,
            RESOLUTION,
            RETRIEVED_AT,
        )

        assert first_pass == {"inserted": 1, "skipped": 0}
        assert _count_test_rows(conn) == 1

        stored_rows = read_sec_ticker_cik_resolutions(conn, TEST_TICKER)
        assert len(stored_rows) == 1
        assert stored_rows[0]["cik"] == "9999999995"
        assert stored_rows[0]["resolution_method"] == "name_search"
        assert stored_rows[0]["matched_name"] == "QuantLab Test Issuer, Inc."

        second_pass = write_sec_ticker_cik_resolution(
            conn,
            RESOLUTION,
            RETRIEVED_AT,
        )

        assert second_pass == {"inserted": 0, "skipped": 1}
        assert _count_test_rows(conn) == 1

    finally:
        conn.rollback()
        conn.close()
