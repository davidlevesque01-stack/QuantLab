-- ============================================================
-- QuantLab
-- Migration 006
-- Nasdaq PostgreSQL Persistence V1.2
--
-- Purpose:
--   Align the PostgreSQL schema with the validated V1.2
--   persistence model.
--
-- V1.2 model:
--
--   RAW HALT identity:
--       symbol + market + halt_date + halt_time + reason_code
--
--   RESUMPTION:
--       one HALT may have multiple source observations
--
--   CORE episode identity:
--       symbol + market + halt_start
--
--   reason_code is descriptive at CORE level and does not
--   participate in CORE identity.
--
-- IMPORTANT:
--   This migration preserves referential integrity while
--   consolidating duplicate RAW rows.
--
-- PostgreSQL requirement:
--   PostgreSQL 15+ is required for UNIQUE NULLS NOT DISTINCT.
--
-- Version: 1.2
-- ============================================================

BEGIN;

-- Serialize this migration with the Nasdaq PostgreSQL
-- persistence transaction.
--
-- Advisory lock key:
--     (716203, 1)
--
-- The lock is transaction-scoped and is released automatically
-- by COMMIT or ROLLBACK.
SELECT pg_advisory_xact_lock(716203, 1);


-- ============================================================
-- 1. RAW NASDAQ TRADE HALT
-- ============================================================
--
-- V1.1 allowed several raw.nasdaq_trade_halt rows for the same
-- logical HALT when resumption information differed.
--
-- V1.2 restores the HALT identity to:
--
--     symbol
--     market
--     halt_date
--     halt_time
--     reason_code
--
-- Before deleting duplicates, build a deterministic mapping
-- from every redundant RAW row to the RAW row that must survive.
--
-- Canonical-row preference:
--
--   1. resumption_date present
--   2. resumption_trade_time present
--   3. resumption_quote_time present
--   4. smallest id
--
-- CORE foreign keys and relationship rows are repointed in
-- section 2 before any RAW row is deleted.
-- ============================================================

CREATE TEMP TABLE _nasdaq_raw_v12_map
ON COMMIT DROP
AS
WITH ranked AS (
    SELECT
        id,
        symbol,
        market,
        halt_date,
        halt_time,
        reason_code,

        FIRST_VALUE(id) OVER (
            PARTITION BY
                symbol,
                market,
                halt_date,
                halt_time,
                reason_code
            ORDER BY
                (resumption_date IS NOT NULL) DESC,
                (resumption_trade_time IS NOT NULL) DESC,
                (resumption_quote_time IS NOT NULL) DESC,
                id ASC
        ) AS keep_id,

        ROW_NUMBER() OVER (
            PARTITION BY
                symbol,
                market,
                halt_date,
                halt_time,
                reason_code
            ORDER BY
                (resumption_date IS NOT NULL) DESC,
                (resumption_trade_time IS NOT NULL) DESC,
                (resumption_quote_time IS NOT NULL) DESC,
                id ASC
        ) AS rn

    FROM raw.nasdaq_trade_halt
)
SELECT
    id AS duplicate_id,
    keep_id
FROM ranked
WHERE rn > 1;


-- Defensive validation:
-- no row may map to itself.

DO $$
DECLARE
    invalid_mapping_count bigint;
BEGIN

    SELECT COUNT(*)
    INTO invalid_mapping_count
    FROM _nasdaq_raw_v12_map
    WHERE duplicate_id = keep_id;

    IF invalid_mapping_count <> 0 THEN
        RAISE EXCEPTION
            'RAW V1.2 mapping validation failed: % rows map to themselves',
            invalid_mapping_count;
    END IF;

END
$$;


-- Defensive validation:
-- every duplicate and every canonical row referenced by the
-- mapping must still exist before relationship migration.

DO $$
DECLARE
    missing_duplicate_rows bigint;
    missing_keep_rows bigint;
BEGIN

    SELECT COUNT(*)
    INTO missing_duplicate_rows
    FROM _nasdaq_raw_v12_map m
    LEFT JOIN raw.nasdaq_trade_halt r
        ON r.id = m.duplicate_id
    WHERE r.id IS NULL;

    SELECT COUNT(*)
    INTO missing_keep_rows
    FROM _nasdaq_raw_v12_map m
    LEFT JOIN raw.nasdaq_trade_halt r
        ON r.id = m.keep_id
    WHERE r.id IS NULL;

    IF missing_duplicate_rows <> 0 THEN
        RAISE EXCEPTION
            'RAW V1.2 mapping validation failed: % duplicate RAW rows are missing',
            missing_duplicate_rows;
    END IF;

    IF missing_keep_rows <> 0 THEN
        RAISE EXCEPTION
            'RAW V1.2 mapping validation failed: % canonical RAW rows are missing',
            missing_keep_rows;
    END IF;

END
$$;


-- ============================================================
-- 2. CORE -> RAW RELATIONSHIPS
-- ============================================================
--
-- Repoint every reference from a duplicate RAW row to its
-- canonical V1.2 RAW row before deleting the duplicate.
--
-- The relationship table may already contain both:
--
--     episode -> duplicate RAW
--     episode -> canonical RAW
--
-- In that case, updating the first relationship directly would
-- violate uq_episode_event. Remove the redundant relationship
-- first.
-- ============================================================


-- ------------------------------------------------------------
-- 2.1 Remove relationship rows that would become duplicates
-- ------------------------------------------------------------

DELETE FROM core.nasdaq_halt_episode_event duplicate_rel
USING _nasdaq_raw_v12_map m
WHERE duplicate_rel.trade_halt_id = m.duplicate_id
  AND EXISTS (
      SELECT 1
      FROM core.nasdaq_halt_episode_event keep_rel
      WHERE keep_rel.episode_id = duplicate_rel.episode_id
        AND keep_rel.trade_halt_id = m.keep_id
  );


-- ------------------------------------------------------------
-- 2.2 Repoint remaining relationship rows
-- ------------------------------------------------------------

UPDATE core.nasdaq_halt_episode_event rel
SET trade_halt_id = m.keep_id
FROM _nasdaq_raw_v12_map m
WHERE rel.trade_halt_id = m.duplicate_id;


-- ------------------------------------------------------------
-- 2.3 Repoint the compatibility FK stored on CORE episode
-- ------------------------------------------------------------

UPDATE core.nasdaq_halt_episode ep
SET trade_halt_id = m.keep_id
FROM _nasdaq_raw_v12_map m
WHERE ep.trade_halt_id = m.duplicate_id;


-- ------------------------------------------------------------
-- 2.4 Validate that no CORE reference still targets a
--     duplicate RAW row
-- ------------------------------------------------------------

DO $$
DECLARE
    remaining_episode_refs bigint;
    remaining_relation_refs bigint;
BEGIN

    SELECT COUNT(*)
    INTO remaining_episode_refs
    FROM core.nasdaq_halt_episode ep
    JOIN _nasdaq_raw_v12_map m
        ON m.duplicate_id = ep.trade_halt_id;

    SELECT COUNT(*)
    INTO remaining_relation_refs
    FROM core.nasdaq_halt_episode_event rel
    JOIN _nasdaq_raw_v12_map m
        ON m.duplicate_id = rel.trade_halt_id;

    IF remaining_episode_refs <> 0 THEN
        RAISE EXCEPTION
            'RAW V1.2 migration failed: % CORE episodes still reference duplicate RAW rows',
            remaining_episode_refs;
    END IF;

    IF remaining_relation_refs <> 0 THEN
        RAISE EXCEPTION
            'RAW V1.2 migration failed: % CORE relationships still reference duplicate RAW rows',
            remaining_relation_refs;
    END IF;

END
$$;


-- ------------------------------------------------------------
-- 2.5 Delete redundant RAW rows
-- ------------------------------------------------------------

DELETE FROM raw.nasdaq_trade_halt r
USING _nasdaq_raw_v12_map m
WHERE r.id = m.duplicate_id;


-- ------------------------------------------------------------
-- 2.6 Install the V1.2 RAW natural key
-- ------------------------------------------------------------

ALTER TABLE raw.nasdaq_trade_halt
DROP CONSTRAINT IF EXISTS
    uq_nasdaq_trade_halt_natural_key;

ALTER TABLE raw.nasdaq_trade_halt
ADD CONSTRAINT uq_nasdaq_trade_halt_natural_key
UNIQUE (
    symbol,
    market,
    halt_date,
    halt_time,
    reason_code
);


-- ------------------------------------------------------------
-- 2.7 Validate RAW uniqueness
-- ------------------------------------------------------------

DO $$
DECLARE
    duplicate_raw_keys bigint;
BEGIN

    SELECT COUNT(*)
    INTO duplicate_raw_keys
    FROM (
        SELECT
            symbol,
            market,
            halt_date,
            halt_time,
            reason_code
        FROM raw.nasdaq_trade_halt
        GROUP BY
            symbol,
            market,
            halt_date,
            halt_time,
            reason_code
        HAVING COUNT(*) > 1
    ) duplicates;

    IF duplicate_raw_keys <> 0 THEN
        RAISE EXCEPTION
            'RAW V1.2 uniqueness validation failed: % duplicate natural keys remain',
            duplicate_raw_keys;
    END IF;

END
$$;


-- ============================================================
-- 3. CORE HALT EPISODE NATURAL KEY
-- ============================================================
--
-- V1.1 CORE identity:
--
--     symbol + market + reason_code + halt_start
--
-- V1.2 CORE identity:
--
--     symbol + market + halt_start
--
-- reason_code becomes descriptive. Multiple Nasdaq reason-code
-- observations may therefore belong to the same logical CORE
-- halt episode.
--
-- Unlike RAW consolidation, this migration does NOT silently
-- merge existing CORE episodes. If duplicate CORE rows already
-- exist under the V1.2 identity, manual review is required.
-- ============================================================


-- ------------------------------------------------------------
-- 3.1 Validate that the V1.2 CORE identity is already unique
-- ------------------------------------------------------------

DO $$
DECLARE
    duplicate_core_keys bigint;
BEGIN

    SELECT COUNT(*)
    INTO duplicate_core_keys
    FROM (
        SELECT
            symbol,
            market,
            halt_start
        FROM core.nasdaq_halt_episode
        GROUP BY
            symbol,
            market,
            halt_start
        HAVING COUNT(*) > 1
    ) duplicates;

    IF duplicate_core_keys <> 0 THEN
        RAISE EXCEPTION
            'CORE V1.2 migration requires manual review: % duplicate (symbol, market, halt_start) keys found',
            duplicate_core_keys;
    END IF;

END
$$;


-- ------------------------------------------------------------
-- 3.2 Replace the V1.1 natural-key constraint
-- ------------------------------------------------------------

ALTER TABLE core.nasdaq_halt_episode
DROP CONSTRAINT IF EXISTS
    uq_nasdaq_halt_episode_natural_key;

ALTER TABLE core.nasdaq_halt_episode
ADD CONSTRAINT uq_nasdaq_halt_episode_natural_key
UNIQUE (
    symbol,
    market,
    halt_start
);


-- ------------------------------------------------------------
-- 3.3 Validate the installed CORE identity
-- ------------------------------------------------------------

DO $$
DECLARE
    duplicate_core_keys bigint;
BEGIN

    SELECT COUNT(*)
    INTO duplicate_core_keys
    FROM (
        SELECT
            symbol,
            market,
            halt_start
        FROM core.nasdaq_halt_episode
        GROUP BY
            symbol,
            market,
            halt_start
        HAVING COUNT(*) > 1
    ) duplicates;

    IF duplicate_core_keys <> 0 THEN
        RAISE EXCEPTION
            'CORE V1.2 uniqueness validation failed: % duplicate natural keys remain',
            duplicate_core_keys;
    END IF;

END
$$;


-- ============================================================
-- 4. RESUMPTION OBSERVATIONS
-- ============================================================
--
-- PostgreSQL UNIQUE normally considers NULL values distinct.
--
-- Nasdaq resumption observations may legitimately contain:
--
--     resumption_quote_time = NULL
--     resumption_trade_time = NULL
--
-- Under the V1.1 constraint, identical observations containing
-- NULL could therefore be inserted repeatedly.
--
-- V1.2:
--   1. removes existing duplicate observations;
--   2. installs UNIQUE NULLS NOT DISTINCT so NULL participates
--      in observation identity as an ordinary comparable value.
-- ============================================================


-- ------------------------------------------------------------
-- 4.1 Deduplicate existing resumption observations
--
-- Keep the smallest id for each exact observation identity.
-- PostgreSQL PARTITION BY groups NULL values together, which is
-- the semantics required by V1.2.
-- ------------------------------------------------------------

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


-- ------------------------------------------------------------
-- 4.2 Replace the old UNIQUE constraint
-- ------------------------------------------------------------

ALTER TABLE raw.nasdaq_resumption
DROP CONSTRAINT IF EXISTS
    uq_nasdaq_resumption_observation;

ALTER TABLE raw.nasdaq_resumption
ADD CONSTRAINT uq_nasdaq_resumption_observation
UNIQUE NULLS NOT DISTINCT (
    symbol,
    market,
    halt_date,
    halt_time,
    reason_code,
    resumption_date,
    resumption_quote_time,
    resumption_trade_time
);


-- ------------------------------------------------------------
-- 4.3 Validate observation uniqueness with NULL-safe grouping
-- ------------------------------------------------------------

DO $$
DECLARE
    duplicate_resumption_keys bigint;
BEGIN

    SELECT COUNT(*)
    INTO duplicate_resumption_keys
    FROM (
        SELECT
            symbol,
            market,
            halt_date,
            halt_time,
            reason_code,
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
            resumption_date,
            resumption_quote_time,
            resumption_trade_time
        HAVING COUNT(*) > 1
    ) duplicates;

    IF duplicate_resumption_keys <> 0 THEN
        RAISE EXCEPTION
            'RESUMPTION V1.2 uniqueness validation failed: % duplicate observations remain',
            duplicate_resumption_keys;
    END IF;

END
$$;


-- ============================================================
-- 5. FINAL VALIDATION
-- ============================================================
--
-- The transaction must not commit unless:
--
--   1. every CORE trade_halt_id references an existing RAW row;
--   2. every relationship references an existing CORE episode;
--   3. every relationship references an existing RAW row;
--   4. no duplicate episode -> RAW relationship exists.
--
-- Any failure raises an exception and rolls back the complete
-- V1.2 migration.
-- ============================================================

DO $$
DECLARE
    broken_episode_raw_refs bigint;
    broken_relation_episode_refs bigint;
    broken_relation_raw_refs bigint;
    duplicate_relation_pairs bigint;
BEGIN

    -- CORE compatibility FK -> RAW

    SELECT COUNT(*)
    INTO broken_episode_raw_refs
    FROM core.nasdaq_halt_episode ep
    LEFT JOIN raw.nasdaq_trade_halt r
        ON r.id = ep.trade_halt_id
    WHERE r.id IS NULL;


    -- Relationship -> CORE

    SELECT COUNT(*)
    INTO broken_relation_episode_refs
    FROM core.nasdaq_halt_episode_event rel
    LEFT JOIN core.nasdaq_halt_episode ep
        ON ep.id = rel.episode_id
    WHERE ep.id IS NULL;


    -- Relationship -> RAW

    SELECT COUNT(*)
    INTO broken_relation_raw_refs
    FROM core.nasdaq_halt_episode_event rel
    LEFT JOIN raw.nasdaq_trade_halt r
        ON r.id = rel.trade_halt_id
    WHERE r.id IS NULL;


    -- Duplicate CORE -> RAW relationships

    SELECT COUNT(*)
    INTO duplicate_relation_pairs
    FROM (
        SELECT
            episode_id,
            trade_halt_id
        FROM core.nasdaq_halt_episode_event
        GROUP BY
            episode_id,
            trade_halt_id
        HAVING COUNT(*) > 1
    ) duplicates;


    IF broken_episode_raw_refs <> 0 THEN
        RAISE EXCEPTION
            'V1.2 validation failed: % broken CORE -> RAW references',
            broken_episode_raw_refs;
    END IF;


    IF broken_relation_episode_refs <> 0 THEN
        RAISE EXCEPTION
            'V1.2 validation failed: % broken relationship -> CORE references',
            broken_relation_episode_refs;
    END IF;


    IF broken_relation_raw_refs <> 0 THEN
        RAISE EXCEPTION
            'V1.2 validation failed: % broken relationship -> RAW references',
            broken_relation_raw_refs;
    END IF;


    IF duplicate_relation_pairs <> 0 THEN
        RAISE EXCEPTION
            'V1.2 validation failed: % duplicate CORE -> RAW relationship pairs',
            duplicate_relation_pairs;
    END IF;

END
$$;


COMMIT;





