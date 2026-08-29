-- ============================================================
-- QuantLab
-- Migration 002
-- CORE episode -> RAW event relationship
--
-- Purpose:
--   Allow one logical CORE halt episode to reference
--   one or more RAW Nasdaq halt events.
--
-- IMPORTANT:
--   This migration is intentionally NON-DESTRUCTIVE.
--   It does not alter or drop the existing
--   core.nasdaq_halt_episode.trade_halt_id column.
--
-- Version: 1.0
-- ============================================================

BEGIN;


-- ============================================================
-- 1. CREATE EPISODE -> RAW LINK TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS core.nasdaq_halt_episode_event (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    episode_id bigint NOT NULL,

    trade_halt_id bigint NOT NULL,

    CONSTRAINT fk_episode_event_episode
        FOREIGN KEY (episode_id)
        REFERENCES core.nasdaq_halt_episode(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_episode_event_raw
        FOREIGN KEY (trade_halt_id)
        REFERENCES raw.nasdaq_trade_halt(id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_episode_event
        UNIQUE (
            episode_id,
            trade_halt_id
        )
);


-- ============================================================
-- 2. INDEXES
-- ============================================================

CREATE INDEX IF NOT EXISTS
    idx_nasdaq_halt_episode_event_episode
ON core.nasdaq_halt_episode_event (
    episode_id
);


CREATE INDEX IF NOT EXISTS
    idx_nasdaq_halt_episode_event_raw
ON core.nasdaq_halt_episode_event (
    trade_halt_id
);


-- ============================================================
-- 3. MIGRATE EXISTING CORE -> RAW RELATIONSHIPS
--
-- Existing CORE rows currently contain exactly one
-- trade_halt_id.
--
-- We preserve those relationships in the new table.
--
-- ON CONFLICT protects against accidental re-execution.
-- ============================================================

INSERT INTO core.nasdaq_halt_episode_event (
    episode_id,
    trade_halt_id
)
SELECT
    e.id,
    e.trade_halt_id
FROM core.nasdaq_halt_episode e
WHERE e.trade_halt_id IS NOT NULL
ON CONFLICT (
    episode_id,
    trade_halt_id
)
DO NOTHING;


-- ============================================================
-- 4. VALIDATION
-- ============================================================

DO $$
DECLARE
    core_count bigint;
    link_count bigint;
BEGIN

    SELECT COUNT(*)
    INTO core_count
    FROM core.nasdaq_halt_episode
    WHERE trade_halt_id IS NOT NULL;


    SELECT COUNT(*)
    INTO link_count
    FROM core.nasdaq_halt_episode_event;


    IF core_count <> link_count THEN

        RAISE EXCEPTION
            'Migration validation failed: CORE rows (%) != relationship rows (%)',
            core_count,
            link_count;

    END IF;

END
$$;


-- ============================================================
-- 5. FINAL REFERENTIAL-INTEGRITY VALIDATION
-- ============================================================

DO $$
DECLARE
    orphan_episode_links bigint;
    orphan_raw_links bigint;
BEGIN

    SELECT COUNT(*)
    INTO orphan_episode_links
    FROM core.nasdaq_halt_episode_event ee
    LEFT JOIN core.nasdaq_halt_episode e
        ON e.id = ee.episode_id
    WHERE e.id IS NULL;


    SELECT COUNT(*)
    INTO orphan_raw_links
    FROM core.nasdaq_halt_episode_event ee
    LEFT JOIN raw.nasdaq_trade_halt r
        ON r.id = ee.trade_halt_id
    WHERE r.id IS NULL;


    IF orphan_episode_links <> 0 THEN

        RAISE EXCEPTION
            'Migration validation failed: % orphan episode links found',
            orphan_episode_links;

    END IF;


    IF orphan_raw_links <> 0 THEN

        RAISE EXCEPTION
            'Migration validation failed: % orphan RAW links found',
            orphan_raw_links;

    END IF;

END
$$;


COMMIT;
