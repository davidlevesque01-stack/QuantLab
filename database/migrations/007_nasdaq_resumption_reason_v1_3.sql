-- ============================================================
-- QuantLab
-- Migration 007
-- Nasdaq Resumption Reason Separation V1.3.1
--
-- Purpose:
--   Separate the HALT reason from the ReasonCode returned by
--   Nasdaq resumedate observations without losing historical
--   RAW source observations.
--
-- Rules:
--   haltdate ReasonCode   -> reason_code
--   resumedate ReasonCode -> resumption_reason_code
--
-- IMPORTANT:
--   Existing reason_code values are preserved.
--   New resumedate observations may legitimately have
--   reason_code = NULL.
--
--   RAW observation identity keeps BOTH reason contexts.
--   This prevents destructive consolidation of source rows
--   that differ only by HALT context.
--
-- PostgreSQL requirement:
--   PostgreSQL 15+ for UNIQUE NULLS NOT DISTINCT.
-- ============================================================

BEGIN;

SELECT pg_advisory_xact_lock(716203, 1);


-- ============================================================
-- 1. ADD RESUMPTION REASON
-- ============================================================

ALTER TABLE raw.nasdaq_resumption
ADD COLUMN IF NOT EXISTS
    resumption_reason_code VARCHAR(20);

-- A resumedate observation does not necessarily carry the
-- original HALT reason, so reason_code becomes optional here.
ALTER TABLE raw.nasdaq_resumption
ALTER COLUMN reason_code DROP NOT NULL;


-- ============================================================
-- 2. REPLACE OBSERVATION IDENTITY
-- ============================================================
--
-- V1.3.1 RAW observation identity:
--
--   symbol
--   market
--   halt_date
--   halt_time
--   reason_code
--   resumption_reason_code
--   resumption_date
--   resumption_quote_time
--   resumption_trade_time
--
-- Both reason fields are retained because RAW represents source
-- observations. No existing rows are merged merely because the
-- new resumption_reason_code column is NULL.
-- ============================================================

ALTER TABLE raw.nasdaq_resumption
DROP CONSTRAINT IF EXISTS
    uq_nasdaq_resumption_observation;

-- Defensive deduplication only for truly identical observations
-- under the complete V1.3.1 identity.
WITH ranked AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY
                symbol,
                market,
                halt_date,
                halt_time,
                reason_code,
                resumption_reason_code,
                resumption_date,
                resumption_quote_time,
                resumption_trade_time
            ORDER BY id ASC
        ) AS rn
    FROM raw.nasdaq_resumption
)
DELETE FROM raw.nasdaq_resumption r
USING ranked
WHERE r.id = ranked.id
  AND ranked.rn > 1;

ALTER TABLE raw.nasdaq_resumption
ADD CONSTRAINT uq_nasdaq_resumption_observation
UNIQUE NULLS NOT DISTINCT (
    symbol,
    market,
    halt_date,
    halt_time,
    reason_code,
    resumption_reason_code,
    resumption_date,
    resumption_quote_time,
    resumption_trade_time
);


-- ============================================================
-- 3. INDEXES
-- ============================================================

DROP INDEX IF EXISTS raw.idx_nasdaq_resumption_halt;

CREATE INDEX idx_nasdaq_resumption_halt
ON raw.nasdaq_resumption (
    symbol,
    market,
    halt_date,
    halt_time
);

CREATE INDEX IF NOT EXISTS
    idx_nasdaq_resumption_reason
ON raw.nasdaq_resumption (
    resumption_reason_code
);


-- ============================================================
-- 4. VALIDATION
-- ============================================================

DO $$
DECLARE
    duplicate_observations bigint;
    invalid_reasonless_rows bigint;
BEGIN

    SELECT COUNT(*)
    INTO duplicate_observations
    FROM (
        SELECT
            symbol,
            market,
            halt_date,
            halt_time,
            reason_code,
            resumption_reason_code,
            resumption_date,
            resumption_quote_time,
            resumption_trade_time
        FROM raw.nasdaq_resumption
        GROUP BY
            symbol,
            market,
            halt_date,
            halt_time,
            reason_code,
            resumption_reason_code,
            resumption_date,
            resumption_quote_time,
            resumption_trade_time
        HAVING COUNT(*) > 1
    ) duplicates;

    IF duplicate_observations <> 0 THEN
        RAISE EXCEPTION
            'V1.3.1 resumption uniqueness validation failed: % duplicate observations',
            duplicate_observations;
    END IF;

    SELECT COUNT(*)
    INTO invalid_reasonless_rows
    FROM raw.nasdaq_resumption
    WHERE reason_code IS NULL
      AND resumption_reason_code IS NULL;

    IF invalid_reasonless_rows <> 0 THEN
        RAISE EXCEPTION
            'V1.3.1 validation failed: % resumption rows have neither HALT nor resumption reason',
            invalid_reasonless_rows;
    END IF;

END
$$;

COMMIT;
