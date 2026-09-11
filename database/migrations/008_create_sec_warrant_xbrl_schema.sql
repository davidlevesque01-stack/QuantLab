-- ============================================================
-- QuantLab
-- Migration 008
-- SEC Warrant XBRL Facts (RAW)
--
-- Purpose:
--   Lossless capture of us-gaap "ClassOfWarrantOrRight*" XBRL facts
--   returned by the SEC EDGAR company-facts API for a given issuer
--   (CIK). This is the RAW layer for the SEC-native warrant discovery
--   and extraction pipeline (SEC-06) — coverage is limited to issuers
--   who tag warrant terms dimensionally in XBRL (notably ex-SPAC
--   issuers since 2021). Full-text/exhibit-based discovery for
--   untagged issuers is separate, deferred follow-up work.
--
-- IMPORTANT:
--   RAW is immutable observation capture, not the normalized CORE
--   warrant model (core.security / core.warrant / core.warrant_term_history),
--   which remains deferred (WRT-06) until enough real data has been
--   inspected across both the SEC-native and DilutionTracker paths.
--
-- PostgreSQL requirement:
--   PostgreSQL 15+ is required for UNIQUE NULLS NOT DISTINCT (instant
--   XBRL facts report only "end", so "period_start" is legitimately
--   NULL and must still participate in observation identity).
--
-- Version: 1.0
-- ============================================================

BEGIN;

CREATE TABLE IF NOT EXISTS raw.sec_warrant_xbrl_fact (
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

    CONSTRAINT uq_sec_warrant_xbrl_fact_observation
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
    idx_sec_warrant_xbrl_fact_cik
ON raw.sec_warrant_xbrl_fact (
    cik
);

CREATE INDEX IF NOT EXISTS
    idx_sec_warrant_xbrl_fact_cik_concept
ON raw.sec_warrant_xbrl_fact (
    cik,
    concept
);

COMMIT;
