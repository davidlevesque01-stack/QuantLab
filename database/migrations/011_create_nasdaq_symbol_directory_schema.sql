-- ============================================================
-- QuantLab
-- Migration 011
-- Nasdaq Symbol Directory (RAW)
--
-- Purpose:
--   Lossless, point-in-time capture of Nasdaq Trader's daily symbol
--   directory files (nasdaqlisted.txt, otherlisted.txt) — the universe
--   of listed securities to track (SEC-03). Nasdaq Trader gives
--   identity/listing metadata only; it never carries warrant/dilution
--   terms (see raw.sec_warrant_xbrl_fact, migration 008, for that).
--
-- IMPORTANT:
--   RAW is immutable observation capture: each run inserts a new
--   timestamped snapshot rather than updating rows in place, matching
--   the project's point-in-time reconstruction requirement. The full
--   raw record is preserved in `payload` (JSONB) for lossless fidelity
--   across both source files, which do not share an identical column
--   set.
--
-- Version: 1.0
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS raw.nasdaq_symbol_directory (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    symbol VARCHAR(20) NOT NULL,
    source_file VARCHAR(20) NOT NULL,

    security_name TEXT,
    exchange VARCHAR(10),
    test_issue VARCHAR(1),
    round_lot_size INTEGER,
    etf VARCHAR(1),

    payload JSONB NOT NULL,

    retrieved_at TIMESTAMPTZ NOT NULL,

    loaded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_nasdaq_symbol_directory_observation
        UNIQUE (
            symbol,
            source_file,
            retrieved_at
        )
);

CREATE INDEX IF NOT EXISTS
    idx_nasdaq_symbol_directory_symbol
ON raw.nasdaq_symbol_directory (
    symbol
);

COMMIT;
