-- ============================================================
-- QuantLab
-- Migration 015
-- SEC Reverse Stock Split Events (RAW)
--
-- Purpose:
--   Capture of reverse (or forward) stock split events found in 8-K
--   filings (items 3.03/5.03) — the fallback discovery path SEC-09/
--   SEC-10 never covers, since they only look at items 1.01/3.02
--   (new securities issuance). Without this, warrant terms already
--   captured in raw.sec_8k_warrant_text_extraction only ever reflect
--   the ORIGINAL issuance terms, never the current split-adjusted
--   terms (confirmed on TNON: a 2026-08-10 1-for-35 reverse split
--   explains a consistent ~35x gap between our raw data and
--   DilutionTracker across three independent warrant series).
--
-- IMPORTANT:
--   Minimum-viable scope (SEC-11): this table only records that a
--   split happened and its ratio/effective date. It does NOT
--   retroactively apply the ratio to existing warrant_text_extraction
--   rows — that requires a CORE-level concept (deferred, ties into
--   WRT-06).
--
-- Version: 1.0
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS raw.sec_reverse_split_event (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cik VARCHAR(10) NOT NULL,
    accession_number VARCHAR(30) NOT NULL,
    document_url TEXT NOT NULL,
    filed_date DATE,
    form_type VARCHAR(20),

    ratio_new INTEGER NOT NULL,
    ratio_old INTEGER NOT NULL,
    effective_date DATE,

    raw_snippet TEXT NOT NULL,

    retrieved_at TIMESTAMPTZ NOT NULL,

    loaded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_sec_reverse_split_event_ratio
        CHECK (ratio_new > 0 AND ratio_old > 0),

    CONSTRAINT uq_sec_reverse_split_event_observation
        UNIQUE (
            cik,
            accession_number,
            raw_snippet
        )
);

CREATE INDEX IF NOT EXISTS
    idx_sec_reverse_split_event_cik
ON raw.sec_reverse_split_event (
    cik
);

COMMIT;
