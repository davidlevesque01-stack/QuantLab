from datetime import datetime, timezone

from shared.database import get_connection

from collectors.warrants.src.warrants_postgresql import (
    read_sec_reverse_split_events,
    write_sec_reverse_split_events,
)


# ============================================================
# QUANTLAB - SEC REVERSE SPLIT EVENT RAW LIVE UPDATE TEST
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


TEST_CIK = "9999999994"

RETRIEVED_AT = datetime(2099, 1, 2, 10, 0, 0, tzinfo=timezone.utc)

EVENTS = [
    {
        "accession_number": "QLTEST-0005",
        "document_url": "https://www.sec.gov/QLTEST-8k.htm",
        "filed_date": "2098-08-10",
        "form_type": "8-K",
        "ratio_new": 1,
        "ratio_old": 35,
        "effective_date": "2098-08-10",
        "raw_snippet": "1-for-35 reverse stock split",
    }
]


def _count_test_rows(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM raw.sec_reverse_split_event WHERE cik = %s;",
            (TEST_CIK,),
        )
        return cur.fetchone()[0]


def test_sec_reverse_split_event_capture_is_idempotent():
    conn = get_connection()

    try:
        existing = _count_test_rows(conn)

        if existing != 0:
            raise RuntimeError(
                "Test data already exists in PostgreSQL. "
                "The previous test may not have been rolled back."
            )

        first_pass = write_sec_reverse_split_events(
            conn,
            TEST_CIK,
            EVENTS,
            RETRIEVED_AT,
        )

        assert first_pass == {"inserted": 1, "skipped": 0}
        assert _count_test_rows(conn) == 1

        stored_rows = read_sec_reverse_split_events(conn, TEST_CIK)
        assert len(stored_rows) == 1
        assert stored_rows[0]["ratio_new"] == 1
        assert stored_rows[0]["ratio_old"] == 35

        second_pass = write_sec_reverse_split_events(
            conn,
            TEST_CIK,
            EVENTS,
            RETRIEVED_AT,
        )

        assert second_pass == {"inserted": 0, "skipped": 1}
        assert _count_test_rows(conn) == 1

    finally:
        conn.rollback()
        conn.close()
