-- ============================================================
-- QuantLab
-- Migration 019
-- Market Data — richer core.market_bar_1m schema (BT-16)
--
-- Purpose:
--   Additive follow-up to migration 018 (BT-01) preparing
--   core.market_bar_1m for a real intraday provider (Massive, BT-11) --
--   see docs/backtesting/BACKTESTING_COMPONENT.md, "Initial logical data
--   model", and docs/backtesting/BACKTESTING_GITHUB_BACKLOG.md#bt-16.
--   018 is never edited retroactively; every new column here is nullable
--   so existing RAW->CORE pass-through inserts (BT-01's
--   collectors/market_data/src/market_data_postgresql.py) keep working
--   unchanged.
--
--   raw.market_bar_1m is intentionally left untouched: it stays a
--   byte-faithful per-source capture (ticker/market/bar_start/OHLCV/
--   source only). The richer, provider-agnostic fields below belong to
--   CORE, consistent with the project's canonical-table principle ("the
--   canonical table carries provenance metadata but never
--   provider-specific business logic").
--
--   `market` (venue letter code) becomes nullable on CORE only, because
--   SIP-consolidated bars (Massive's `minute_aggs_v1`) have no single
--   venue per bar; `market_scope` ('CONSOLIDATED_US' for SIP data) is the
--   replacement concept going forward. `market` is kept rather than
--   removed -- no retroactive rewrite of an applied migration.
--
--   `security_id` is added as a nullable column only (no FK constraint
--   yet -- core.security does not exist until CS-07 lands). It stays
--   unpopulated until core.security exists and a backfill is done;
--   `ticker` remains the working identifier until then. The FK
--   constraint itself is added in a later migration once CS-07 defines
--   core.security's shape.
--
--   KNOWN OPEN POINT for BT-11: uq_market_bar_1m_core_natural_key is
--   (ticker, market, bar_start). Postgres treats NULLs as distinct for
--   uniqueness purposes, so once `market` is NULL for every SIP-sourced
--   row, this constraint no longer prevents duplicate canonical bars for
--   the same (ticker, bar_start). BT-11 must resolve this explicitly
--   (e.g. a natural key keyed on (ticker, bar_start) once `market` is
--   fully retired in practice, or a partial unique index) before real
--   ingestion relies on ON CONFLICT for idempotency -- not silently
--   inherited from this schema-only migration.
--
-- Version: 1.0
-- ============================================================

BEGIN;

ALTER TABLE core.market_bar_1m
    ALTER COLUMN market DROP NOT NULL;

ALTER TABLE core.market_bar_1m
    ADD COLUMN security_id BIGINT,
    ADD COLUMN market_scope VARCHAR(30),
    ADD COLUMN session VARCHAR(20),
    ADD COLUMN transaction_count INTEGER,
    ADD COLUMN source_provider VARCHAR(30),
    ADD COLUMN source_dataset VARCHAR(100),
    ADD COLUMN dataset_version VARCHAR(30),
    ADD COLUMN ingestion_run_id VARCHAR(64);

ALTER TABLE core.market_bar_1m
    ADD CONSTRAINT chk_market_bar_1m_core_session
    CHECK (
        session IS NULL
        OR session IN ('PRE_MARKET', 'REGULAR', 'AFTER_HOURS')
    );

ALTER TABLE core.market_bar_1m
    ADD CONSTRAINT chk_market_bar_1m_core_transaction_count
    CHECK (transaction_count IS NULL OR transaction_count >= 0);

COMMENT ON COLUMN core.market_bar_1m.security_id IS
    'Nullable, no FK yet -- core.security does not exist until CS-07. '
    'FK constraint to be added once CS-07 defines core.security.';

COMMENT ON COLUMN core.market_bar_1m.market_scope IS
    'e.g. CONSOLIDATED_US for SIP-consolidated data. Replaces market as '
    'the primary scope concept for provider-sourced (non-venue-specific) bars.';

COMMENT ON COLUMN core.market_bar_1m.session IS
    'Pre-market / regular / after-hours, computed at ingestion from '
    'shared/calendar/trading_calendar.get_session_bounds().';

COMMENT ON COLUMN core.market_bar_1m.source_provider IS
    'e.g. MASSIVE.';

COMMENT ON COLUMN core.market_bar_1m.source_dataset IS
    'e.g. us_stocks_sip/minute_aggs_v1.';

COMMENT ON COLUMN core.market_bar_1m.transaction_count IS
    'Number of trades aggregated into this bar, optional -- only when the '
    'source reports it.';

COMMENT ON COLUMN core.market_bar_1m.dataset_version IS
    'Provider dataset version (e.g. Massive minute_aggs_v1).';

COMMENT ON COLUMN core.market_bar_1m.ingestion_run_id IS
    'Identifier of the ingestion run that produced this row (traceability, '
    'no fixed format imposed).';

COMMIT;
