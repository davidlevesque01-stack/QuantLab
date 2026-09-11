from datetime import datetime, timezone

from shared.database import get_connection

from collectors.warrants.src.warrants_postgresql import (
    write_nasdaq_symbol_directory,
)


# ============================================================
# QUANTLAB - NASDAQ SYMBOL DIRECTORY RAW LIVE UPDATE TEST
# ============================================================
#
# Objectif :
#
#   1. Première ingestion    -> INSERT
#   2. Réingestion identique -> no-op (ON CONFLICT DO NOTHING)
#   3. ROLLBACK final        -> aucune donnée de test persistée
#
# Utilise volontairement un symbole réservé à QuantLab pour éviter
# toute collision avec un titre réel.
#
# ============================================================


TEST_SYMBOL = "QLV08TEST"

RETRIEVED_AT = datetime(2099, 1, 2, 10, 0, 0, tzinfo=timezone.utc)

RECORDS = [
    {
        "symbol": TEST_SYMBOL,
        "source_file": "nasdaqlisted",
        "security_name": "QuantLab Test Issue",
        "exchange": "Q",
        "test_issue": "Y",
        "round_lot_size": "100",
        "etf": "N",
        "payload": {"Symbol": TEST_SYMBOL, "Security Name": "QuantLab Test Issue"},
    }
]


def _count_test_rows(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM raw.nasdaq_symbol_directory WHERE symbol = %s;",
            (TEST_SYMBOL,),
        )
        return cur.fetchone()[0]


def test_nasdaq_symbol_directory_capture_is_idempotent():
    conn = get_connection()

    try:
        existing = _count_test_rows(conn)

        if existing != 0:
            raise RuntimeError(
                "Test data already exists in PostgreSQL. "
                "The previous test may not have been rolled back."
            )

        first_pass = write_nasdaq_symbol_directory(
            conn,
            RECORDS,
            RETRIEVED_AT,
        )

        assert first_pass == {"inserted": 1, "skipped": 0}
        assert _count_test_rows(conn) == 1

        second_pass = write_nasdaq_symbol_directory(
            conn,
            RECORDS,
            RETRIEVED_AT,
        )

        assert second_pass == {"inserted": 0, "skipped": 1}
        assert _count_test_rows(conn) == 1

    finally:
        conn.rollback()
        conn.close()
