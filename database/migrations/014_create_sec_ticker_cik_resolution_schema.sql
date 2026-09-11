-- ============================================================
-- QuantLab
-- Migration 014
-- SEC Ticker -> CIK Resolution Audit Trail (RAW)
--
-- Purpose:
--   Point-in-time capture of how each ticker was resolved to a CIK
--   (SEC-14) — direct company_tickers.json lookup ("ticker_map") vs.
--   name-search fallback ("name_search") for delisted/acquired issuers
--   no longer in the live ticker file. Kept for audit: a name-search
--   match is inferential (see sec_company_name_search.find_best_match),
--   so every resolution decision should be traceable and re-checkable,
--   not silently trusted.
--
-- IMPORTANT:
--   RAW is immutable observation capture: each run inserts a new
--   timestamped snapshot rather than updating rows in place.
--
-- Version: 1.0
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS raw.sec_ticker_cik_resolution (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    ticker VARCHAR(20) NOT NULL,
    cik VARCHAR(10),

    resolution_method VARCHAR(20) NOT NULL,
    issuer_name_used TEXT,
    matched_name TEXT,

    retrieved_at TIMESTAMPTZ NOT NULL,

    loaded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_sec_ticker_cik_resolution_method
        CHECK (resolution_method IN ('ticker_map', 'name_search', 'not_found')),

    CONSTRAINT uq_sec_ticker_cik_resolution_observation
        UNIQUE (
            ticker,
            retrieved_at
        )
);

CREATE INDEX IF NOT EXISTS
    idx_sec_ticker_cik_resolution_ticker
ON raw.sec_ticker_cik_resolution (
    ticker
);

COMMIT;
