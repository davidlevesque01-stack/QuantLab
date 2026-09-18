-- ============================================================
-- QuantLab
-- Migration 020
-- Market Data — NULL-market dedup fix for raw/core.market_bar_1m (BT-11)
--
-- Purpose:
--   Migration 019 made core.market_bar_1m.market nullable to accommodate
--   SIP-consolidated bars (Massive minute_aggs_v1, BT-11) that carry no
--   single venue per bar, and its own header flagged the unresolved
--   consequence: uq_market_bar_1m_core_natural_key is
--   UNIQUE (ticker, market, bar_start), and Postgres treats every NULL as
--   distinct from every other NULL for uniqueness purposes -- so once
--   `market` is NULL for every Massive-sourced row, that constraint no
--   longer prevents duplicate canonical bars for the same
--   (ticker, bar_start), and ON CONFLICT (ticker, market, bar_start)
--   never fires for those rows on a rerun.
--
--   raw.market_bar_1m has the identical latent problem once MassiveAdapter
--   leaves `market` unset for SIP-consolidated rows: forcing a fabricated
--   venue code there would violate the "RAW is a byte-faithful per-source
--   capture" principle (018's own header), since Massive's flat file has
--   no venue column at all. So raw.market_bar_1m.market is made nullable
--   here too, mirroring 019's treatment of CORE, and gets the same kind
--   of partial unique index.
--
--   Both existing full-column unique constraints
--   (uq_market_bar_1m_raw_natural_key, uq_market_bar_1m_core_natural_key)
--   are left completely untouched -- they keep deduplicating every row
--   where `market` is still populated (CSVAdapter/legacy rows, BT-01).
--   This migration only ADDS two new PARTIAL unique indexes covering the
--   market-IS-NULL case.
--
--   collectors/market_data/src/market_data_postgresql.py's
--   write_market_bars() and write_core_market_bars() each partition their
--   incoming batch into two groups by whether `market` is NULL, and issue
--   two separate INSERT ... ON CONFLICT statements per batch -- Postgres
--   requires the ON CONFLICT arbiter to match one specific unique index
--   per statement, and a partial index's predicate must be restated in
--   the INSERT's ON CONFLICT clause for inference to match it.
--
-- Version: 1.0
-- ============================================================

BEGIN;

ALTER TABLE raw.market_bar_1m
    ALTER COLUMN market DROP NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS
    uq_market_bar_1m_raw_null_market_natural_key
ON raw.market_bar_1m (
    ticker,
    bar_start,
    source
)
WHERE market IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS
    uq_market_bar_1m_core_null_market_natural_key
ON core.market_bar_1m (
    ticker,
    bar_start
)
WHERE market IS NULL;

COMMENT ON INDEX raw.uq_market_bar_1m_raw_null_market_natural_key IS
    'Partial unique index covering SIP-consolidated bars (market IS NULL, '
    'e.g. Massive minute_aggs_v1, BT-11) where '
    'uq_market_bar_1m_raw_natural_key (ticker, market, bar_start, source) '
    'cannot deduplicate because Postgres treats NULL as distinct for '
    'uniqueness. Non-NULL-market rows keep relying on '
    'uq_market_bar_1m_raw_natural_key.';

COMMENT ON INDEX core.uq_market_bar_1m_core_null_market_natural_key IS
    'Partial unique index covering SIP-consolidated bars (market IS NULL, '
    'e.g. Massive minute_aggs_v1, BT-11) where '
    'uq_market_bar_1m_core_natural_key (ticker, market, bar_start) cannot '
    'deduplicate because Postgres treats NULL as distinct for uniqueness. '
    'Non-NULL-market rows keep relying on uq_market_bar_1m_core_natural_key.';

COMMIT;
