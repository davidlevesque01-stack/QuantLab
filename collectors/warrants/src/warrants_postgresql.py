"""Persistance PostgreSQL du composant warrants.

Verrous advisory réservés (classid 716203, registre partagé avec
nasdaq_halts) :
    (716203, 1) -> nasdaq_halts
    (716203, 3) -> warrants / SEC warrant XBRL RAW capture
    (716203, 4) -> warrants / SEC shares outstanding XBRL RAW capture
    (716203, 5) -> warrants / SEC 8-K warrant exhibit discovery RAW capture
    (716203, 6) -> warrants / Nasdaq symbol directory RAW capture
    (716203, 7) -> warrants / SEC 8-K warrant text extraction RAW capture
    (716203, 8) -> warrants / SEC ticker->CIK resolution audit trail RAW capture
    (716203, 9) -> warrants / SEC reverse stock split event RAW capture

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


def read_sec_8k_warrant_text_extractions(conn, cik):
    """Lit raw.sec_8k_warrant_text_extraction pour un CIK donné (lecture seule)."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                accession_number,
                document_url,
                filed_date,
                form_type,
                kind,
                label,
                share_quantity,
                exercise_price,
                expiration_years,
                raw_snippet
            FROM raw.sec_8k_warrant_text_extraction
            WHERE cik = %s
            ORDER BY accession_number, kind;
            """,
            (cik,),
        )

        columns = [description[0] for description in cur.description]

        return [dict(zip(columns, row)) for row in cur.fetchall()]


def write_sec_8k_warrant_text_extractions(conn, cik, observations, retrieved_at):
    """
    Insère dans raw.sec_8k_warrant_text_extraction les observations
    extraites du texte des 8-K (voir
    sec_8k_warrant_text_extraction.discover_and_extract_warrant_terms_for_cik),
    sur une connexion/transaction fournie par l'appelant (ne commit pas).

    Capture RAW immuable, extraction heuristique : une réingestion
    identique est un no-op (ON CONFLICT DO NOTHING).
    """

    rows = []
    seen = set()

    for observation in observations:

        row = (
            cik,
            observation["accession_number"],
            observation["document_url"],
            observation.get("filed_date"),
            observation.get("form_type"),
            observation["kind"],
            observation.get("label"),
            observation.get("share_quantity"),
            observation.get("exercise_price"),
            observation.get("expiration_years"),
            observation["raw_snippet"],
            retrieved_at,
        )

        key = (cik, observation["accession_number"], observation["kind"], observation["raw_snippet"])

        if key not in seen:
            seen.add(key)
            rows.append(row)

    if not rows:
        return {"inserted": 0, "skipped": 0}

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO raw.sec_8k_warrant_text_extraction (
                cik,
                accession_number,
                document_url,
                filed_date,
                form_type,
                kind,
                label,
                share_quantity,
                exercise_price,
                expiration_years,
                raw_snippet,
                retrieved_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (
                cik,
                accession_number,
                kind,
                raw_snippet
            ) DO NOTHING;
            """,
            rows,
        )

        inserted = cur.rowcount

    return {
        "inserted": inserted,
        "skipped": len(rows) - inserted,
    }


def persist_sec_8k_warrant_text_extractions(cik, observations, retrieved_at):
    """
    Ouvre sa propre connexion, prend le verrou advisory (716203, 7) et
    persiste les observations extraites du texte des 8-K pour un CIK
    (commit à la sortie du context manager).
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s, %s);",
                (716203, 7),
            )

        return write_sec_8k_warrant_text_extractions(
            conn,
            cik,
            observations,
            retrieved_at,
        )


def read_sec_ticker_cik_resolutions(conn, ticker):
    """Lit raw.sec_ticker_cik_resolution pour un ticker donné (lecture seule)."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                cik,
                resolution_method,
                issuer_name_used,
                matched_name,
                retrieved_at
            FROM raw.sec_ticker_cik_resolution
            WHERE ticker = %s
            ORDER BY retrieved_at;
            """,
            (ticker,),
        )

        columns = [description[0] for description in cur.description]

        return [dict(zip(columns, row)) for row in cur.fetchall()]


def write_sec_ticker_cik_resolution(conn, resolution, retrieved_at):
    """
    Insère dans raw.sec_ticker_cik_resolution une décision de résolution
    (voir sec_cik_resolution.resolve_cik_with_fallback), sur une
    connexion/transaction fournie par l'appelant (ne commit pas).

    Capture RAW immuable : une réingestion identique est un no-op
    (ON CONFLICT DO NOTHING).
    """

    row = (
        resolution["ticker"],
        resolution.get("cik"),
        resolution["method"],
        resolution.get("issuer_name_used"),
        resolution.get("matched_name"),
        retrieved_at,
    )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO raw.sec_ticker_cik_resolution (
                ticker,
                cik,
                resolution_method,
                issuer_name_used,
                matched_name,
                retrieved_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (
                ticker,
                retrieved_at
            ) DO NOTHING;
            """,
            row,
        )

        inserted = cur.rowcount

    return {
        "inserted": inserted,
        "skipped": 1 - inserted,
    }


def persist_sec_ticker_cik_resolution(resolution, retrieved_at):
    """
    Ouvre sa propre connexion, prend le verrou advisory (716203, 8) et
    persiste une décision de résolution ticker->CIK (commit à la sortie
    du context manager).
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s, %s);",
                (716203, 8),
            )

        return write_sec_ticker_cik_resolution(
            conn,
            resolution,
            retrieved_at,
        )


def read_issue_names_for_tickers(conn, tickers):
    """
    Lit core.nasdaq_halt_episode.issue_name pour une liste de tickers
    (lecture seule) — la source de nom d'émetteur déjà connue et fiable
    utilisée comme repli de résolution CIK (SEC-14), pour ne jamais
    deviner un nom de société.

    Retourne {ticker: issue_name}, en prenant le nom le plus récent en
    cas de plusieurs épisodes HALT pour un même symbole.
    """

    if not tickers:
        return {}

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (symbol)
                symbol,
                issue_name
            FROM core.nasdaq_halt_episode
            WHERE symbol = ANY(%s)
              AND issue_name IS NOT NULL
            ORDER BY symbol, halt_start DESC;
            """,
            (list(tickers),),
        )

        return {symbol: issue_name for symbol, issue_name in cur.fetchall()}


def read_sec_reverse_split_events(conn, cik):
    """Lit raw.sec_reverse_split_event pour un CIK donné (lecture seule)."""

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                accession_number,
                document_url,
                filed_date,
                form_type,
                ratio_new,
                ratio_old,
                effective_date,
                raw_snippet
            FROM raw.sec_reverse_split_event
            WHERE cik = %s
            ORDER BY filed_date;
            """,
            (cik,),
        )

        columns = [description[0] for description in cur.description]

        return [dict(zip(columns, row)) for row in cur.fetchall()]


def write_sec_reverse_split_events(conn, cik, events, retrieved_at):
    """
    Insère dans raw.sec_reverse_split_event les événements de split
    trouvés (voir
    sec_reverse_split_extraction.discover_and_extract_reverse_splits_for_cik),
    sur une connexion/transaction fournie par l'appelant (ne commit pas).

    Capture RAW immuable : une réingestion identique est un no-op
    (ON CONFLICT DO NOTHING).
    """

    rows = []
    seen = set()

    for event in events:

        row = (
            cik,
            event["accession_number"],
            event["document_url"],
            event.get("filed_date"),
            event.get("form_type"),
            event["ratio_new"],
            event["ratio_old"],
            event.get("effective_date"),
            event["raw_snippet"],
            retrieved_at,
        )

        key = (cik, event["accession_number"], event["raw_snippet"])

        if key not in seen:
            seen.add(key)
            rows.append(row)

    if not rows:
        return {"inserted": 0, "skipped": 0}

    with conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO raw.sec_reverse_split_event (
                cik,
                accession_number,
                document_url,
                filed_date,
                form_type,
                ratio_new,
                ratio_old,
                effective_date,
                raw_snippet,
                retrieved_at
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            ON CONFLICT (
                cik,
                accession_number,
                raw_snippet
            ) DO NOTHING;
            """,
            rows,
        )

        inserted = cur.rowcount

    return {
        "inserted": inserted,
        "skipped": len(rows) - inserted,
    }


def persist_sec_reverse_split_events(cik, events, retrieved_at):
    """
    Ouvre sa propre connexion, prend le verrou advisory (716203, 9) et
    persiste les événements de split pour un CIK (commit à la sortie du
    context manager).
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s, %s);",
                (716203, 9),
            )

        return write_sec_reverse_split_events(
            conn,
            cik,
            events,
            retrieved_at,
        )
