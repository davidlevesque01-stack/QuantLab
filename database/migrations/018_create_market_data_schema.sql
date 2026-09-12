-- ============================================================
-- QuantLab
-- Migration 018
-- Market Data — raw.market_bar_1m / core.market_bar_1m (BT-01)
--
-- Purpose:
--   1-minute OHLCV bars for the Historical Intraday Predictive Replay
--   Engine (see docs/backtesting/BACKTESTING_COMPONENT.md). Only 1-minute
--   bars are ever persisted -- every larger timeframe (2m/5m/15m/.../
--   daily) is computed on demand by the Aggregation Engine (BT-02), never
--   sourced from a provider's own aggregation.
--
--   `bar_start` is a naive TIMESTAMP representing Nasdaq's local
--   wall-clock time (America/New_York), per the timezone convention
--   formalized in BT-00 (docs/database.md Section 15,
--   shared/calendar/trading_calendar.py NASDAQ_TZ).
--
-- IMPORTANT:
--   raw.market_bar_1m is immutable RAW capture: a bar is never modified
--   once inserted for a given (ticker, market, bar_start, source) --
--   distinct sources may each carry their own row for the same bar.
--   core.market_bar_1m holds the canonical bar per (ticker, market,
--   bar_start). For the BT-01 vertical slice (a single stub/CSV adapter),
--   CORE is a direct pass-through of RAW -- multi-source reconciliation is
--   deferred to BT-11 (real provider integration).
--
--   The OHLC/volume CHECK constraints below encode the same invariants
--   the Source/RAW validation ticket (BT-12) will later re-verify at
--   ingestion time; they are the last line of defense here, per the
--   project's "PostgreSQL constraints remain the final protection for
--   data integrity" principle.
--
-- Version: 1.0
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS raw.market_bar_1m (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ticker VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    bar_start TIMESTAMP NOT NULL,

    open NUMERIC(18, 6) NOT NULL,
    high NUMERIC(18, 6) NOT NULL,
    low NUMERIC(18, 6) NOT NULL,
    close NUMERIC(18, 6) NOT NULL,
    volume BIGINT NOT NULL,

    source VARCHAR(30) NOT NULL,

    loaded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_market_bar_1m_raw_natural_key
        UNIQUE (
            ticker,
            market,
            bar_start,
            source
        ),

    CONSTRAINT chk_market_bar_1m_raw_ohlc
        CHECK (
            high >= open
            AND high >= close
            AND high >= low
            AND low <= open
            AND low <= close
        ),

    CONSTRAINT chk_market_bar_1m_raw_volume
        CHECK (volume >= 0)
);

CREATE INDEX IF NOT EXISTS
    idx_market_bar_1m_raw_ticker_bar_start
ON raw.market_bar_1m (
    ticker,
    bar_start
);

CREATE TABLE IF NOT EXISTS core.market_bar_1m (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ticker VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,
    bar_start TIMESTAMP NOT NULL,

    open NUMERIC(18, 6) NOT NULL,
    high NUMERIC(18, 6) NOT NULL,
    low NUMERIC(18, 6) NOT NULL,
    close NUMERIC(18, 6) NOT NULL,
    volume BIGINT NOT NULL,

    source VARCHAR(30) NOT NULL,

    loaded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_market_bar_1m_core_natural_key
        UNIQUE (
            ticker,
            market,
            bar_start
        ),

    CONSTRAINT chk_market_bar_1m_core_ohlc
        CHECK (
            high >= open
            AND high >= close
            AND high >= low
            AND low <= open
            AND low <= close
        ),

    CONSTRAINT chk_market_bar_1m_core_volume
        CHECK (volume >= 0)
);

CREATE INDEX IF NOT EXISTS
    idx_market_bar_1m_core_ticker_bar_start
ON core.market_bar_1m (
    ticker,
    bar_start
);

COMMIT;
