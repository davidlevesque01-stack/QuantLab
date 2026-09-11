-- ============================================================
-- QuantLab
-- Migration 009
-- SEC Shares Outstanding XBRL Facts (RAW)
--
-- Purpose:
--   Lossless capture of the dei:EntityCommonStockSharesOutstanding XBRL
--   fact returned by the SEC EDGAR company-facts API for a given issuer
--   (CIK). Unlike warrant terms (raw.sec_warrant_xbrl_fact, migration
--   008), this concept is reported on the cover page of every 10-K/10-Q
--   filer, so coverage is expected to be broad and independent of
--   DilutionTracker (SEC-01 / SEC-02).
--
-- IMPORTANT:
--   RAW is immutable observation capture, not the normalized CORE
--   model. core.security remains deferred (WRT-06).
--
-- PostgreSQL requirement:
--   PostgreSQL 15+ is required for UNIQUE NULLS NOT DISTINCT (instant
--   XBRL facts report only "end", so "period_start" is legitimately
--   NULL and must still participate in observation identity).
--
-- Version: 1.0
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS raw.sec_shares_outstanding_fact (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    cik VARCHAR(10) NOT NULL,
    concept VARCHAR(200) NOT NULL,
    unit VARCHAR(50) NOT NULL,

    fact_value NUMERIC,

    period_start DATE,
    period_end DATE,

    form VARCHAR(20),
    filed_date DATE,
    accession_number VARCHAR(30),
    fiscal_year INTEGER,
    fiscal_period VARCHAR(10),

    retrieved_at TIMESTAMPTZ NOT NULL,

    loaded_at TIMESTAMPTZ NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_sec_shares_outstanding_fact_observation
        UNIQUE NULLS NOT DISTINCT (
            cik,
            concept,
            unit,
            accession_number,
            period_start,
            period_end
        )
);

CREATE INDEX IF NOT EXISTS
    idx_sec_shares_outstanding_fact_cik
ON raw.sec_shares_outstanding_fact (
    cik
);

COMMIT;
