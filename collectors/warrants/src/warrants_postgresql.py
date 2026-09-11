"""Persistance PostgreSQL du composant warrants.

Verrous advisory réservés (classid 716203, registre partagé avec
nasdaq_halts) :
    (716203, 1) -> nasdaq_halts
    (716203, 3) -> warrants / SEC XBRL RAW capture

L'objid 2 est réservé pour la capture RAW DilutionTracker (WRT-04b, à
venir) afin de conserver un registre cohérent entre les deux sources.
"""

from __future__ import annotations

from shared.database.connection import get_connection


def write_sec_warrant_xbrl_facts(conn, cik, observations, retrieved_at):
    """
    Insère dans raw.sec_warrant_xbrl_fact les faits XBRL "ClassOfWarrantOrRight"
    extraits pour un CIK donné (voir sec_warrant_xbrl.extract_warrant_facts),
    sur une connexion/transaction fournie par l'appelant (ne commit pas).

    Capture RAW immuable : une réingestion identique est un no-op
    (ON CONFLICT DO NOTHING), aucune ligne existante n'est modifiée.
    """

    rows = []
    seen = set()

    for observation in observations:

        row = (
            cik,
            observation["concept"],
            observation["unit"],
            observation.get("value"),
            observation.get("period_start"),
            observation.get("period_end"),
            observation.get("form"),
            observation.get("filed"),
            observation.get("accession_number"),
            observation.get("fiscal_year"),
            observation.get("fiscal_period"),
            retrieved_at,
        )

        key = row[:6]

        if key not in seen:
            seen.add(key)
            rows.append(row)

    if not rows:
        return {"inserted": 0, "skipped": 0}

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO raw.sec_warrant_xbrl_fact (
                cik,
                concept,
                unit,
                fact_value,
                period_start,
                period_end,
                form,
                filed_date,
                accession_number,
                fiscal_year,
                fiscal_period,
                retrieved_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (
                cik,
                concept,
                unit,
                accession_number,
                period_start,
                period_end
            ) DO NOTHING;
            """,
            rows,
        )

        inserted = cur.rowcount

    return {
        "inserted": inserted,
        "skipped": len(rows) - inserted,
    }


def persist_sec_warrant_xbrl_facts(cik, observations, retrieved_at):
    """
    Ouvre sa propre connexion, prend le verrou advisory (716203, 3) et
    persiste les faits XBRL de warrants pour un CIK (commit à la sortie
    du context manager).
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s, %s);",
                (716203, 3),
            )

        return write_sec_warrant_xbrl_facts(
            conn,
            cik,
            observations,
            retrieved_at,
        )
