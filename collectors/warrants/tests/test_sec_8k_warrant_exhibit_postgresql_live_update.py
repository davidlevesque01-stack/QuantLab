from datetime import datetime, timezone

from shared.database import get_connection

from collectors.warrants.src.warrants_postgresql import (
    write_sec_8k_warrant_exhibits,
)


# ============================================================
# QUANTLAB - SEC 8-K WARRANT EXHIBIT RAW LIVE UPDATE TEST
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


TEST_CIK = "9999999997"

RETRIEVED_AT = datetime(2099, 1, 2, 10, 0, 0, tzinfo=timezone.utc)

EXHIBITS = [
    {
        "accession_number": "QLTEST-0003",
        "filing_date": "2098-08-31",
        "form_type": "8-K",
        "item_codes": "items 1.01, 3.02",
        "filing_index_url": "https://www.sec.gov/QLTEST-index.htm",
        "exhibit_seq": 3,
        "exhibit_type": "EX-4.1",
        "description": "FORM OF PRE-FUNDED WARRANT",
        "document_url": "https://www.sec.gov/QLTEST-ex4-1.htm",
    }
]


def _count_test_rows(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM raw.sec_8k_warrant_exhibit WHERE cik = %s;",
            (TEST_CIK,),
        )
        return cur.fetchone()[0]


def test_sec_8k_warrant_exhibit_capture_is_idempotent():
    conn = get_connection()

    try:
        existing = _count_test_rows(conn)

        if existing != 0:
            raise RuntimeError(
                "Test data already exists in PostgreSQL. "
                "The previous test may not have been rolled back."
            )

        first_pass = write_sec_8k_warrant_exhibits(
            conn,
            TEST_CIK,
            EXHIBITS,
            RETRIEVED_AT,
        )

        assert first_pass == {"inserted": 1, "skipped": 0}
        assert _count_test_rows(conn) == 1

        second_pass = write_sec_8k_warrant_exhibits(
            conn,
            TEST_CIK,
            EXHIBITS,
            RETRIEVED_AT,
        )

        assert second_pass == {"inserted": 0, "skipped": 1}
        assert _count_test_rows(conn) == 1

    finally:
        conn.rollback()
        conn.close()
