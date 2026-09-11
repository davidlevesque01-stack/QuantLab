from datetime import datetime, timezone

from shared.database import get_connection

from collectors.warrants.src.warrants_postgresql import (
    write_sec_shares_outstanding_facts,
)


# ============================================================
# QUANTLAB - SEC SHARES OUTSTANDING XBRL RAW LIVE UPDATE TEST
# ============================================================
#
# Objectif :
#
#   1. Première ingestion    -> INSERT
#   2. Réingestion identique -> no-op (ON CONFLICT DO NOTHING)
#   3. ROLLBACK final        -> aucune donnée de test persistée
#
# Utilise volontairement un CIK réservé à QuantLab pour éviter toute
# collision avec un émetteur réel.
#
# ============================================================


TEST_CIK = "9999999998"

RETRIEVED_AT = datetime(2099, 1, 2, 10, 0, 0, tzinfo=timezone.utc)

OBSERVATIONS = [
    {
        "concept": "EntityCommonStockSharesOutstanding",
        "unit": "shares",
        "value": 10000000,
        "period_start": None,
        "period_end": "2098-06-30",
        "form": "10-Q",
        "filed": "2098-08-01",
        "accession_number": "QLTEST-0002",
        "fiscal_year": 2098,
        "fiscal_period": "Q2",
    }
]


def _count_test_rows(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM raw.sec_shares_outstanding_fact WHERE cik = %s;",
            (TEST_CIK,),
        )
        return cur.fetchone()[0]


def test_sec_shares_outstanding_capture_is_idempotent():
    conn = get_connection()

    try:
        existing = _count_test_rows(conn)

        if existing != 0:
            raise RuntimeError(
                "Test data already exists in PostgreSQL. "
                "The previous test may not have been rolled back."
            )

        first_pass = write_sec_shares_outstanding_facts(
            conn,
            TEST_CIK,
            OBSERVATIONS,
            RETRIEVED_AT,
        )

        assert first_pass == {"inserted": 1, "skipped": 0}
        assert _count_test_rows(conn) == 1

        second_pass = write_sec_shares_outstanding_facts(
            conn,
            TEST_CIK,
            OBSERVATIONS,
            RETRIEVED_AT,
        )

        assert second_pass == {"inserted": 0, "skipped": 1}
        assert _count_test_rows(conn) == 1

    finally:
        conn.rollback()
        conn.close()
