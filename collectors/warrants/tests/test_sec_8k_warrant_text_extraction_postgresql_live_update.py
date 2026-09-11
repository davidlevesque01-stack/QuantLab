from datetime import datetime, timezone

from shared.database import get_connection

from collectors.warrants.src.warrants_postgresql import (
    write_sec_8k_warrant_text_extractions,
)


# ============================================================
# QUANTLAB - SEC 8-K WARRANT TEXT EXTRACTION RAW LIVE UPDATE TEST
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


TEST_CIK = "9999999996"

RETRIEVED_AT = datetime(2099, 1, 2, 10, 0, 0, tzinfo=timezone.utc)

OBSERVATIONS = [
    {
        "accession_number": "QLTEST-0004",
        "document_url": "https://www.sec.gov/QLTEST-8k.htm",
        "kind": "exercise_price",
        "label": "Each Series A",
        "exercise_price": 5.02,
        "raw_snippet": "Each Series A Warrant has an exercise price of $5.02 per share",
    }
]


def _count_test_rows(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM raw.sec_8k_warrant_text_extraction WHERE cik = %s;",
            (TEST_CIK,),
        )
        return cur.fetchone()[0]


def test_sec_8k_warrant_text_extraction_capture_is_idempotent():
    conn = get_connection()

    try:
        existing = _count_test_rows(conn)

        if existing != 0:
            raise RuntimeError(
                "Test data already exists in PostgreSQL. "
                "The previous test may not have been rolled back."
            )

        first_pass = write_sec_8k_warrant_text_extractions(
            conn,
            TEST_CIK,
            OBSERVATIONS,
            RETRIEVED_AT,
        )

        assert first_pass == {"inserted": 1, "skipped": 0}
        assert _count_test_rows(conn) == 1

        second_pass = write_sec_8k_warrant_text_extractions(
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
