"""Persistance PostgreSQL du composant warrants.

Verrous advisory réservés (classid 716203, registre partagé avec
nasdaq_halts) :
    (716203, 1) -> nasdaq_halts
    (716203, 3) -> warrants / SEC warrant XBRL RAW capture
    (716203, 4) -> warrants / SEC shares outstanding XBRL RAW capture
    (716203, 5) -> warrants / SEC 8-K warrant exhibit discovery RAW capture
    (716203, 6) -> warrants / Nasdaq symbol directory RAW capture

L'objid 2 est réservé pour la capture RAW DilutionTracker (WRT-04b, à
venir) afin de conserver un registre cohérent entre les sources.
"""

from __future__ import annotations

from psycopg.types.json import Jsonb

from shared.database.connection import get_connection


def _read_xbrl_facts(conn, table, cik):
    """
    Lit toutes les lignes de `table` pour un CIK donné, sous forme de
    liste de dicts. `table` est toujours un littéral interne connu
    (jamais une entrée utilisateur) — voir les deux appelants ci-dessous.
    """

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT
                concept,
                unit,
                fact_value,
                period_start,
                period_end,
                form,
                filed_date,
                accession_number,
                fiscal_year,
                fiscal_period
            FROM {table}
            WHERE cik = %s
            ORDER BY concept, period_end;
            """,
            (cik,),
        )

        columns = [description[0] for description in cur.description]

        return [dict(zip(columns, row)) for row in cur.fetchall()]


def read_sec_warrant_xbrl_facts(conn, cik):
    """Lit raw.sec_warrant_xbrl_fact pour un CIK donné (lecture seule)."""

    return _read_xbrl_facts(conn, "raw.sec_warrant_xbrl_fact", cik)


def read_sec_shares_outstanding_facts(conn, cik):
    """Lit raw.sec_shares_outstanding_fact pour un CIK donné (lecture seule)."""

    return _read_xbrl_facts(conn, "raw.sec_shares_outstanding_fact", cik)


def _build_xbrl_fact_rows(cik, observations, retrieved_at):
    """
    Construit les lignes (cik, concept, unit, ...) à insérer à partir
    d'observations XBRL aplaties (sec_xbrl_facts.extract_facts), en
    dédupliquant sur l'identité d'observation RAW.

    Partagé entre raw.sec_warrant_xbrl_fact et
    raw.sec_shares_outstanding_fact, qui ont le même schéma de colonnes.
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

    return rows


def write_sec_warrant_xbrl_facts(conn, cik, observations, retrieved_at):
    """
    Insère dans raw.sec_warrant_xbrl_fact les faits XBRL "ClassOfWarrantOrRight"
    extraits pour un CIK donné (voir sec_warrant_xbrl.extract_warrant_facts),
    sur une connexion/transaction fournie par l'appelant (ne commit pas).

    Capture RAW immuable : une réingestion identique est un no-op
    (ON CONFLICT DO NOTHING), aucune ligne existante n'est modifiée.
    """

    rows = _build_xbrl_fact_rows(cik, observations, retrieved_at)

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


def write_sec_shares_outstanding_facts(conn, cik, observations, retrieved_at):
    """
    Insère dans raw.sec_shares_outstanding_fact les faits XBRL
    dei:EntityCommonStockSharesOutstanding extraits pour un CIK donné (voir
    sec_shares_outstanding.extract_shares_outstanding_facts), sur une
    connexion/transaction fournie par l'appelant (ne commit pas).

    Capture RAW immuable : une réingestion identique est un no-op
    (ON CONFLICT DO NOTHING), aucune ligne existante n'est modifiée.
    """

    rows = _build_xbrl_fact_rows(cik, observations, retrieved_at)

    if not rows:
        return {"inserted": 0, "skipped": 0}

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO raw.sec_shares_outstanding_fact (
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


def persist_sec_shares_outstanding_facts(cik, observations, retrieved_at):
    """
    Ouvre sa propre connexion, prend le verrou advisory (716203, 4) et
    persiste les faits XBRL de shares outstanding pour un CIK (commit à
    la sortie du context manager).
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s, %s);",
                (716203, 4),
            )

        return write_sec_shares_outstanding_facts(
            conn,
            cik,
            observations,
            retrieved_at,
        )


def read_sec_8k_warrant_exhibits(conn, cik):
    """Lit raw.sec_8k_warrant_exhibit pour un CIK donné (lecture seule)."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                accession_number,
                filing_date,
                form_type,
                item_codes,
                exhibit_seq,
                exhibit_type,
                description,
                document_url,
                filing_index_url
            FROM raw.sec_8k_warrant_exhibit
            WHERE cik = %s
            ORDER BY filing_date, exhibit_seq;
            """,
            (cik,),
        )

        columns = [description[0] for description in cur.description]

        return [dict(zip(columns, row)) for row in cur.fetchall()]


def write_sec_8k_warrant_exhibits(conn, cik, exhibits, retrieved_at):
    """
    Insère dans raw.sec_8k_warrant_exhibit les exhibits de 8-K
    probablement liés à un warrant (voir
    sec_8k_warrant_discovery.discover_warrant_exhibits_for_cik), sur une
    connexion/transaction fournie par l'appelant (ne commit pas).

    Capture RAW immuable : une réingestion identique est un no-op
    (ON CONFLICT DO NOTHING).
    """

    rows = []
    seen = set()

    for exhibit in exhibits:

        row = (
            cik,
            exhibit["accession_number"],
            exhibit.get("filing_date"),
            exhibit.get("form_type"),
            exhibit.get("item_codes"),
            exhibit["exhibit_seq"],
            exhibit.get("exhibit_type"),
            exhibit.get("description"),
            exhibit["document_url"],
            exhibit.get("filing_index_url"),
            retrieved_at,
        )

        key = (cik, exhibit["accession_number"], exhibit["exhibit_seq"])

        if key not in seen:
            seen.add(key)
            rows.append(row)

    if not rows:
        return {"inserted": 0, "skipped": 0}

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO raw.sec_8k_warrant_exhibit (
                cik,
                accession_number,
                filing_date,
                form_type,
                item_codes,
                exhibit_seq,
                exhibit_type,
                description,
                document_url,
                filing_index_url,
                retrieved_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (
                cik,
                accession_number,
                exhibit_seq
            ) DO NOTHING;
            """,
            rows,
        )

        inserted = cur.rowcount

    return {
        "inserted": inserted,
        "skipped": len(rows) - inserted,
    }


def persist_sec_8k_warrant_exhibits(cik, exhibits, retrieved_at):
    """
    Ouvre sa propre connexion, prend le verrou advisory (716203, 5) et
    persiste les exhibits de warrants découverts pour un CIK (commit à
    la sortie du context manager).
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s, %s);",
                (716203, 5),
            )

        return write_sec_8k_warrant_exhibits(
            conn,
            cik,
            exhibits,
            retrieved_at,
        )


def write_nasdaq_symbol_directory(conn, records, retrieved_at):
    """
    Insère dans raw.nasdaq_symbol_directory un snapshot horodaté de
    l'annuaire des titres (voir nasdaq_symbol_directory.fetch_and_parse_symbol_directory),
    sur une connexion/transaction fournie par l'appelant (ne commit pas).

    Capture RAW immuable : chaque exécution insère un nouveau snapshot
    (pas de mise à jour en place) — cohérent avec le principe
    point-in-time du projet. Idempotent à l'intérieur d'une même
    exécution (ON CONFLICT DO NOTHING sur symbol/source_file/retrieved_at).
    """

    rows = []
    seen = set()

    for record in records:

        row = (
            record["symbol"],
            record["source_file"],
            record.get("security_name"),
            record.get("exchange"),
            record.get("test_issue"),
            _parse_int_or_none(record.get("round_lot_size")),
            record.get("etf"),
            Jsonb(record.get("payload") or {}),
            retrieved_at,
        )

        key = (record["symbol"], record["source_file"])

        if key not in seen:
            seen.add(key)
            rows.append(row)

    if not rows:
        return {"inserted": 0, "skipped": 0}

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO raw.nasdaq_symbol_directory (
                symbol,
                source_file,
                security_name,
                exchange,
                test_issue,
                round_lot_size,
                etf,
                payload,
                retrieved_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (
                symbol,
                source_file,
                retrieved_at
            ) DO NOTHING;
            """,
            rows,
        )

        inserted = cur.rowcount

    return {
        "inserted": inserted,
        "skipped": len(rows) - inserted,
    }


def _parse_int_or_none(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def persist_nasdaq_symbol_directory(records, retrieved_at):
    """
    Ouvre sa propre connexion, prend le verrou advisory (716203, 6) et
    persiste le snapshot de l'annuaire Nasdaq (commit à la sortie du
    context manager).
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s, %s);",
                (716203, 6),
            )

        return write_nasdaq_symbol_directory(
            conn,
            records,
            retrieved_at,
        )
