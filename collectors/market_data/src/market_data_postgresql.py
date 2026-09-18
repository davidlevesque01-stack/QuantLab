"""Market data PostgreSQL persistence (BT-01).

QuantLab advisory lock registry (classid 716203):
    (716203, 1) -> Nasdaq HALT/resumption/episode persistence
    (716203, 2) -> reserved for DilutionTracker RAW capture (not yet used)
    (716203, 3) -> warrants / SEC warrant XBRL RAW capture
    (716203, 4) -> warrants / SEC shares outstanding RAW capture
    (716203, 5) -> warrants / SEC 8-K warrant exhibit RAW capture
    (716203, 6) -> warrants / Nasdaq symbol directory RAW capture
    (716203, 7) -> warrants / SEC 8-K warrant text extraction RAW capture
    (716203, 8) -> warrants / SEC ticker->CIK resolution audit trail RAW capture
    (716203, 9) -> warrants / SEC reverse stock split event RAW capture
    (716203, 10) -> market data / market_bar_1m RAW+CORE capture (this module)

See docs/database.md Section 21 for the authoritative registry.
"""

from __future__ import annotations

from shared.database.connection import get_connection


def _raw_row(bar, source):
    return (
        bar["ticker"],
        bar["market"],
        bar["bar_start"],
        bar["open"],
        bar["high"],
        bar["low"],
        bar["close"],
        bar["volume"],
        source,
    )


_RAW_INSERT_COLUMNS = """
    ticker,
    market,
    bar_start,
    open,
    high,
    low,
    close,
    volume,
    source
"""

_RAW_INSERT_VALUES = "%s, %s, %s, %s, %s, %s, %s, %s, %s"


def write_market_bars(conn, bars, source):
    """
    Inserts 1-minute OHLCV bars into raw.market_bar_1m for a given source,
    on a connection/transaction supplied by the caller (does not commit).

    Immutable RAW capture: a bar for a given (ticker, market, bar_start,
    source) is never modified once inserted -- a rerun is a no-op
    (ON CONFLICT DO NOTHING), consistent with the project's RAW-is-immutable
    principle. Distinct sources may each carry their own row for the same
    bar; canonical selection across sources happens in CORE.

    `market` is NULL for SIP-consolidated providers (e.g. Massive, BT-11)
    that carry no single venue per bar. Postgres treats every NULL as
    distinct for uniqueness, so uq_market_bar_1m_raw_natural_key
    (ticker, market, bar_start, source) cannot deduplicate those rows --
    migration 020 adds a partial unique index covering market IS NULL
    instead. A batch mixing both kinds of rows is split into two
    executemany calls, one per arbiter index (see migration 020's header).
    """

    if not bars:
        return {"inserted": 0, "skipped": 0}

    with_market = [_raw_row(b, source) for b in bars if b["market"] is not None]
    without_market = [_raw_row(b, source) for b in bars if b["market"] is None]

    inserted = 0

    with conn.cursor() as cur:
        if with_market:
            cur.executemany(
                f"""
                INSERT INTO raw.market_bar_1m ({_RAW_INSERT_COLUMNS})
                VALUES ({_RAW_INSERT_VALUES})
                ON CONFLICT (
                    ticker,
                    market,
                    bar_start,
                    source
                ) DO NOTHING;
                """,
                with_market,
            )
            inserted += cur.rowcount

        if without_market:
            cur.executemany(
                f"""
                INSERT INTO raw.market_bar_1m ({_RAW_INSERT_COLUMNS})
                VALUES ({_RAW_INSERT_VALUES})
                ON CONFLICT (
                    ticker,
                    bar_start,
                    source
                ) WHERE market IS NULL DO NOTHING;
                """,
                without_market,
            )
            inserted += cur.rowcount

    return {
        "inserted": inserted,
        "skipped": len(bars) - inserted,
    }


def _core_row(bar, source):
    return (
        bar["ticker"],
        bar["market"],
        bar["bar_start"],
        bar["open"],
        bar["high"],
        bar["low"],
        bar["close"],
        bar["volume"],
        source,
        bar.get("security_id"),
        bar.get("market_scope"),
        bar.get("session"),
        bar.get("transaction_count"),
        bar.get("source_provider"),
        bar.get("source_dataset"),
        bar.get("dataset_version"),
        bar.get("ingestion_run_id"),
    )


_CORE_INSERT_COLUMNS = """
    ticker,
    market,
    bar_start,
    open,
    high,
    low,
    close,
    volume,
    source,
    security_id,
    market_scope,
    session,
    transaction_count,
    source_provider,
    source_dataset,
    dataset_version,
    ingestion_run_id
"""

_CORE_INSERT_VALUES = "%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s"


def write_core_market_bars(conn, bars, source):
    """
    Inserts the canonical 1-minute bar into core.market_bar_1m.

    MVP simplification: with a single active adapter, the CORE row is a
    direct pass-through of the RAW row for that source -- there is no
    multi-source reconciliation logic yet. Once a second provider is wired
    in (BT-11), canonical source selection must be made explicit here
    rather than silently relying on insertion order.

    The migration-019 provenance/enrichment columns (security_id,
    market_scope, session, transaction_count, source_provider,
    source_dataset, dataset_version, ingestion_run_id) are all optional --
    read via bar.get(...), defaulting to NULL -- so the original 8-key
    CSVAdapter bar shape (BT-01) keeps working unchanged.

    `market` is NULL for SIP-consolidated providers (e.g. Massive, BT-11).
    Postgres treats every NULL as distinct for uniqueness, so
    uq_market_bar_1m_core_natural_key (ticker, market, bar_start) cannot
    deduplicate those rows -- migration 020 adds a partial unique index
    covering market IS NULL instead. A batch mixing both kinds of rows is
    split into two executemany calls, one per arbiter index (see migration
    020's header).
    """

    if not bars:
        return {"inserted": 0, "skipped": 0}

    with_market = [_core_row(b, source) for b in bars if b["market"] is not None]
    without_market = [_core_row(b, source) for b in bars if b["market"] is None]

    inserted = 0

    with conn.cursor() as cur:
        if with_market:
            cur.executemany(
                f"""
                INSERT INTO core.market_bar_1m ({_CORE_INSERT_COLUMNS})
                VALUES ({_CORE_INSERT_VALUES})
                ON CONFLICT (
                    ticker,
                    market,
                    bar_start
                ) DO NOTHING;
                """,
                with_market,
            )
            inserted += cur.rowcount

        if without_market:
            cur.executemany(
                f"""
                INSERT INTO core.market_bar_1m ({_CORE_INSERT_COLUMNS})
                VALUES ({_CORE_INSERT_VALUES})
                ON CONFLICT (
                    ticker,
                    bar_start
                ) WHERE market IS NULL DO NOTHING;
                """,
                without_market,
            )
            inserted += cur.rowcount

    return {
        "inserted": inserted,
        "skipped": len(bars) - inserted,
    }


def persist_market_bars(bars, source):
    """
    Opens its own connection, takes advisory lock (716203, 10), and
    persists 1-minute bars to both raw.market_bar_1m and core.market_bar_1m
    (commits on exit of the context manager).
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(%s, %s);",
                (716203, 10),
            )

        raw_result = write_market_bars(conn, bars, source)
        core_result = write_core_market_bars(conn, bars, source)

        return {"raw": raw_result, "core": core_result}
