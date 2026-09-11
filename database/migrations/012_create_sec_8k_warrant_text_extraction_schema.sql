-- ============================================================
-- QuantLab
-- Migration 012
-- SEC 8-K Warrant Text Extraction (RAW)
--
-- Purpose:
--   Heuristic, regex-based capture of warrant terms (share quantity,
--   exercise price, expiration) found in the narrative text of an 8-K
--   body (SEC-10) — the deal-level numbers live there, not in the
--   "FORM OF ... WARRANT" exhibit (a blank template), as discovered
--   validating TNON's 2026-08-31 8-K against DilutionTracker.
--
-- IMPORTANT:
--   This is heuristic text extraction, not a canonical value. Every
--   row keeps its raw_snippet for human verification — never treat a
--   row here as ground truth without checking the snippet against the
--   source document. Extraction patterns are validated against one
--   real filing (TNON); generalization to other issuers'/law firms'
--   phrasing is expected to require incremental refinement.
--
-- Version: 1.0
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS raw.sec_8k_warrant_text_extraction (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cik VARCHAR(10) NOT NULL,
    accession_number VARCHAR(30) NOT NULL,
    document_url TEXT NOT NULL,

    kind VARCHAR(30) NOT NULL,
    label VARCHAR(200),
    share_quantity BIGINT,
    exercise_price NUMERIC,
    expiration_years INTEGER,

    raw_snippet TEXT NOT NULL,

    retrieved_at TIMESTAMPTZ NOT NULL,

    loaded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_sec_8k_warrant_text_extraction_kind
        CHECK (kind IN ('share_quantity', 'exercise_price', 'expiration_years')),

    CONSTRAINT uq_sec_8k_warrant_text_extraction_observation
        UNIQUE (
            cik,
            accession_number,
            kind,
            raw_snippet
        )
);

CREATE INDEX IF NOT EXISTS
    idx_sec_8k_warrant_text_extraction_cik
ON raw.sec_8k_warrant_text_extraction (
    cik
);

COMMIT;
