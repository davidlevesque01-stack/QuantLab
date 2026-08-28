from datetime import datetime

from shared.database import get_connection

from collectors.nasdaq_halts.src.nasdaq_postgresql import (
    VERSION,
    write_trade_halts,
    write_halt_episodes,
)


# ============================================================
# QUANTLAB - NASDAQ POSTGRESQL LIVE UPDATE TEST
# ============================================================
#
# Objectif :
#
#   1. HALT ouvert       -> INSERT
#   2. HALT complété     -> UPDATE
#   3. HALT identique    -> UNCHANGED
#   4. Données régressives / NULL -> aucune perte d'information
#   5. ROLLBACK final    -> aucune donnée de test persistée
#
# Ce test utilise volontairement une date future et un symbole
# réservé à QuantLab afin d'éviter toute collision avec Nasdaq.
#
# ============================================================


TEST_SYMBOL = "QLV08TEST"
TEST_MARKET = "NASDAQ"
TEST_REASON_CODE = "T1"

HALT_START = datetime(
    2099,
    1,
    2,
    10,
    0,
    0,
    123000,
)

HALT_END = datetime(
    2099,
    1,
    2,
    10,
    5,
    0,
)


def build_open_event():
    """
    Première observation :
    le HALT existe, mais aucune reprise n'est encore connue.
    """

    return {
        "symbol": TEST_SYMBOL,
        "issue_name": "QuantLab PostgreSQL V0.8 Test",
        "market": TEST_MARKET,
        "reason_code": TEST_REASON_CODE,
        "halt_date": "01/02/2099",
        "halt_time": "10:00:00.123",
        "resumption_date": None,
        "resumption_quote_time": None,
        "resumption_trade_time": None,
        "pause_threshold_price": None,
        "halt_start": HALT_START,
        "halt_end": None,
        "source_file": "test_live_open.xml",
    }


def build_open_episode():
    """
    Episode correspondant à la première observation ouverte.
    """

    return {
        "episode_id": "HTEST0001",
        "symbol": TEST_SYMBOL,
        "issue_name": "QuantLab PostgreSQL V0.8 Test",
        "market": TEST_MARKET,
        "reason_code": TEST_REASON_CODE,
        "halt_start": HALT_START,
        "halt_end": None,
        "duration_minutes": "",
        "halt_at_close": "UNKNOWN",
    }


def build_completed_event():
    """
    Deuxième observation du même HALT.

    La clé naturelle RAW demeure identique mais les informations
    de reprise sont maintenant disponibles.
    """

    return {
        "symbol": TEST_SYMBOL,
        "issue_name": "QuantLab PostgreSQL V0.8 Test",
        "market": TEST_MARKET,
        "reason_code": TEST_REASON_CODE,
        "halt_date": "01/02/2099",
        "halt_time": "10:00:00.123",
        "resumption_date": "01/02/2099",
        "resumption_quote_time": "10:04:00",
        "resumption_trade_time": "10:05:00",
        "pause_threshold_price": None,
        "halt_start": HALT_START,
        "halt_end": HALT_END,
        "source_file": "test_live_completed.xml",
    }


def build_completed_episode():
    """
    Episode final après réception de l'heure de reprise.
    """

    return {
        "episode_id": "HTEST0001",
        "symbol": TEST_SYMBOL,
        "issue_name": "QuantLab PostgreSQL V0.8 Test",
        "market": TEST_MARKET,
        "reason_code": TEST_REASON_CODE,
        "halt_start": HALT_START,
        "halt_end": HALT_END,
        "duration_minutes": 5.0,
        "halt_at_close": "NO",
    }


def query_database_state(conn):
    """
    Retourne l'état RAW et CORE de l'événement de test.
    """

    with conn.cursor() as cur:

        cur.execute(
            """
            SELECT
                id,
                symbol,
                halt_date,
                halt_time,
                resumption_date,
                resumption_quote_time,
                resumption_trade_time,
                source_file
            FROM raw.nasdaq_trade_halt
            WHERE symbol = %s
              AND halt_date = %s
              AND halt_time = %s
              AND reason_code = %s
              AND market = %s;
            """,
            (
                TEST_SYMBOL,
                HALT_START.date(),
                HALT_START.time(),
                TEST_REASON_CODE,
                TEST_MARKET,
            ),
        )

        raw_row = cur.fetchone()

        if raw_row is None:
            return None, None

        raw_id = raw_row[0]

        cur.execute(
            """
            SELECT
                trade_halt_id,
                symbol,
                halt_start,
                halt_end,
                duration_minutes,
                halt_close_status,
                collector_episode_id
            FROM core.nasdaq_halt_episode
            WHERE trade_halt_id = %s;
            """,
            (
                raw_id,
            ),
        )

        core_row = cur.fetchone()

    return raw_row, core_row


def print_counts(
    label,
    raw_result,
    core_result,
):
    """
    Affichage standardisé des compteurs.
    """

    (
        raw_inserted,
        raw_updated,
        raw_unchanged,
        _,
    ) = raw_result

    (
        core_inserted,
        core_updated,
        core_unchanged,
    ) = core_result

    print()
    print(label)
    print("-" * len(label))

    print(
        f"RAW  inserted / updated / unchanged : "
        f"{raw_inserted} / "
        f"{raw_updated} / "
        f"{raw_unchanged}"
    )

    print(
        f"CORE inserted / updated / unchanged : "
        f"{core_inserted} / "
        f"{core_updated} / "
        f"{core_unchanged}"
    )


def main():

    print()
    print(
        "============================================================"
    )
    print(
        f"QUANTLAB - POSTGRESQL LIVE UPDATE TEST V{VERSION}"
    )
    print(
        "============================================================"
    )

    conn = get_connection()

    try:

        # ====================================================
        # ÉTAPE 0 - VÉRIFICATION PRÉALABLE
        # ====================================================

        raw_before, core_before = (
            query_database_state(
                conn
            )
        )

        if (
            raw_before is not None
            or core_before is not None
        ):

            raise RuntimeError(
                "Test data already exists in PostgreSQL. "
                "The previous test may not have been rolled back."
            )

        print()
        print(
            "Précondition : aucune donnée de test présente ✓"
        )

        # ====================================================
        # ÉTAPE 1 - HALT OUVERT
        # ====================================================

        open_event = (
            build_open_event()
        )

        open_episode = (
            build_open_episode()
        )

        raw_result = (
            write_trade_halts(
                conn,
                [open_event],
            )
        )

        raw_ids = raw_result[3]

        core_result = (
            write_halt_episodes(
                conn,
                [open_episode],
                [open_event],
                raw_ids,
            )
        )

        print_counts(
            "ÉTAPE 1 - HALT OUVERT",
            raw_result,
            core_result,
        )

        assert raw_result[0:3] == (
            1,
            0,
            0,
        )

        assert core_result == (
            1,
            0,
            0,
        )

        raw_row, core_row = (
            query_database_state(
                conn
            )
        )

        assert raw_row is not None
        assert core_row is not None

        assert (
            raw_row[4] is None
        )

        assert (
            raw_row[5] is None
        )

        assert (
            raw_row[6] is None
        )

        assert (
            raw_row[7]
            == "test_live_open.xml"
        )

        assert (
            core_row[3] is None
        )

        assert (
            core_row[4] is None
        )

        assert (
            core_row[5]
            == "UNKNOWN"
        )

        print(
            "Validation HALT ouvert : PASS ✓"
        )

        # ====================================================
        # ÉTAPE 2 - HALT COMPLÉTÉ
        # ====================================================

        completed_event = (
            build_completed_event()
        )

        completed_episode = (
            build_completed_episode()
        )

        raw_result = (
            write_trade_halts(
                conn,
                [completed_event],
            )
        )

        raw_ids = raw_result[3]

        core_result = (
            write_halt_episodes(
                conn,
                [completed_episode],
                [completed_event],
                raw_ids,
            )
        )

        print_counts(
            "ÉTAPE 2 - HALT COMPLÉTÉ",
            raw_result,
            core_result,
        )

        assert raw_result[0:3] == (
            0,
            1,
            0,
        )

        assert core_result == (
            0,
            1,
            0,
        )

        raw_row, core_row = (
            query_database_state(
                conn
            )
        )

        assert (
            raw_row[4]
            == HALT_END.date()
        )

        assert (
            raw_row[5]
            == datetime.strptime(
                "10:04:00",
                "%H:%M:%S",
            ).time()
        )

        assert (
            raw_row[6]
            == HALT_END.time()
        )

        # Le premier snapshot doit rester la provenance
        # actuellement conservée dans RAW.
        assert (
            raw_row[7]
            == "test_live_open.xml"
        )

        assert (
            core_row[3]
            == HALT_END
        )

        assert (
            core_row[4]
            is not None
        )

        assert (
            core_row[5]
            == "NO"
        )

        print(
            "Validation NULL -> valeur : PASS ✓"
        )

        print(
            "Validation source_file premier snapshot : PASS ✓"
        )

        # ====================================================
        # ÉTAPE 3 - MÊMES DONNÉES
        # ====================================================

        raw_result = (
            write_trade_halts(
                conn,
                [completed_event],
            )
        )

        raw_ids = raw_result[3]

        core_result = (
            write_halt_episodes(
                conn,
                [completed_episode],
                [completed_event],
                raw_ids,
            )
        )

        print_counts(
            "ÉTAPE 3 - RÉEXÉCUTION IDENTIQUE",
            raw_result,
            core_result,
        )

        assert raw_result[0:3] == (
            0,
            0,
            1,
        )

        assert core_result == (
            0,
            0,
            1,
        )

        print(
            "Validation idempotence : PASS ✓"
        )

        # ====================================================
        # ÉTAPE 4 - OBSERVATION RÉGRESSIVE
        # ====================================================
        #
        # On simule la réception ultérieure d'une observation
        # incomplète du même HALT.
        #
        # Les valeurs déjà connues ne doivent pas disparaître.
        # UNKNOWN ne doit pas remplacer le statut final NO.
        # ====================================================

        regressive_event = (
            build_open_event()
        )

        regressive_event[
            "source_file"
        ] = "test_live_regressive.xml"

        regressive_episode = (
            build_open_episode()
        )

        raw_result = (
            write_trade_halts(
                conn,
                [regressive_event],
            )
        )

        raw_ids = raw_result[3]

        core_result = (
            write_halt_episodes(
                conn,
                [regressive_episode],
                [regressive_event],
                raw_ids,
            )
        )

        print_counts(
            "ÉTAPE 4 - PROTECTION CONTRE RÉGRESSION",
            raw_result,
            core_result,
        )

        assert raw_result[0:3] == (
            0,
            0,
            1,
        )

        assert core_result == (
            0,
            0,
            1,
        )

        raw_row, core_row = (
            query_database_state(
                conn
            )
        )

        # Les données de reprise doivent toujours exister.
        assert (
            raw_row[4]
            == HALT_END.date()
        )

        assert (
            raw_row[6]
            == HALT_END.time()
        )

        # Le premier snapshot demeure la provenance RAW.
        assert (
            raw_row[7]
            == "test_live_open.xml"
        )

        # CORE ne doit pas régresser.
        assert (
            core_row[3]
            == HALT_END
        )

        assert (
            core_row[5]
            == "NO"
        )

        print(
            "Validation valeur connue -> NULL protégée : PASS ✓"
        )

        print(
            "Validation NO -> UNKNOWN protégée : PASS ✓"
        )

        # ====================================================
        # RÉSULTAT
        # ====================================================

        print()
        print(
            "============================================================"
        )
        print(
            "TOUS LES TESTS V0.8 : PASS ✓"
        )
        print(
            "============================================================"
        )

    finally:

        # ====================================================
        # ROLLBACK OBLIGATOIRE
        # ====================================================
        #
        # Aucune donnée artificielle ne doit rester dans DEV,
        # même si une assertion ou une exception survient.
        # ====================================================

        conn.rollback()

        conn.close()

        print()
        print(
            "ROLLBACK effectué."
        )

        print(
            "Aucune donnée de test n'a été conservée."
        )


if __name__ == "__main__":
    main()
