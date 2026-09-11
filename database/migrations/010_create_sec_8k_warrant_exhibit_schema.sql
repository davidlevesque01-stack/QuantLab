-- ============================================================
-- QuantLab
-- Migration 010
-- SEC 8-K Warrant Exhibit Discovery (RAW)
--
-- Purpose:
--   Lossless capture of 8-K exhibits that plausibly define new warrant
--   terms (SEC-09) — the fallback discovery path for warrants that are
--   never captured by SEC-06's XBRL extraction, because 8-K inline XBRL
--   tagging is limited to cover-page facts and never reaches
--   footnote-level "ClassOfWarrantOrRight" concepts.
--
-- IMPORTANT:
--   This is discovery only: it records WHICH exhibit documents likely
--   describe a warrant (by 8-K item codes 1.01/3.02 and an exhibit
--   description matching /WARRANT/i), with a direct link to the
--   document, for manual review or a future text-extraction pass. It
--   does NOT parse the exhibit's legal prose into numeric terms
--   (exercise price, quantity, expiration) — that remains explicitly
--   deferred follow-up work.
--
-- Version: 1.0
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS raw.sec_8k_warrant_exhibit (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cik VARCHAR(10) NOT NULL,
    accession_number VARCHAR(30) NOT NULL,
    filing_date DATE,
    form_type VARCHAR(20),
    item_codes TEXT,

    exhibit_seq INTEGER NOT NULL,
    exhibit_type VARCHAR(20),
    description TEXT,
    document_url TEXT NOT NULL,
    filing_index_url TEXT,

    retrieved_at TIMESTAMPTZ NOT NULL,

    loaded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_sec_8k_warrant_exhibit_observation
        UNIQUE (
            cik,
            accession_number,
            exhibit_seq
        )
);

CREATE INDEX IF NOT EXISTS
    idx_sec_8k_warrant_exhibit_cik
ON raw.sec_8k_warrant_exhibit (
    cik
);

COMMIT;
