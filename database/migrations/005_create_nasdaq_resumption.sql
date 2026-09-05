-- ============================================================
-- QuantLab
-- Migration 005
-- Nasdaq Resumption Observations
--
-- Purpose:
--   Store one or more resumption observations for a HALT.
--
-- IMPORTANT:
--   Resumption observations are NOT HALT identities.
--   A single HALT may have multiple resumption observations.
--
-- Version: 1.0
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS raw.nasdaq_resumption (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    symbol VARCHAR(20) NOT NULL,
    market VARCHAR(10) NOT NULL,

    halt_date DATE NOT NULL,
    halt_time TIME NOT NULL,

    reason_code VARCHAR(20) NOT NULL,

    resumption_date DATE NOT NULL,
    resumption_quote_time TIME,
    resumption_trade_time TIME,

    source_file TEXT,

    collected_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_nasdaq_resumption_observation
        UNIQUE (
            symbol,
            market,
            halt_date,
            halt_time,
            reason_code,
            resumption_date,
            resumption_quote_time,
            resumption_trade_time
        )
);

CREATE INDEX IF NOT EXISTS
    idx_nasdaq_resumption_halt
ON raw.nasdaq_resumption (
    symbol,
    market,
    halt_date,
    halt_time,
    reason_code
);

CREATE INDEX IF NOT EXISTS
    idx_nasdaq_resumption_date
ON raw.nasdaq_resumption (
    resumption_date
);

COMMIT;
