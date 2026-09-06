-- QuantLab - Nasdaq V1.3 non-regression checks
-- READ-ONLY validation script
-- Safe to prepare/run after resumedate backfill is complete.

-- 1. Table counts
SELECT 'raw.nasdaq_trade_halt' AS object_name, COUNT(*) AS row_count
FROM raw.nasdaq_trade_halt
UNION ALL
SELECT 'raw.nasdaq_resumption', COUNT(*)
FROM raw.nasdaq_resumption
UNION ALL
SELECT 'core.nasdaq_halt_episode', COUNT(*)
FROM core.nasdaq_halt_episode
UNION ALL
SELECT 'core.nasdaq_halt_episode_event', COUNT(*)
FROM core.nasdaq_halt_episode_event
ORDER BY 1;

-- 2. Broken foreign-key style references
SELECT COUNT(*) AS broken_core_trade_halt_refs
FROM core.nasdaq_halt_episode ep
LEFT JOIN raw.nasdaq_trade_halt h
  ON h.id = ep.trade_halt_id
WHERE h.id IS NULL;

SELECT COUNT(*) AS broken_relation_episode_refs
FROM core.nasdaq_halt_episode_event rel
LEFT JOIN core.nasdaq_halt_episode ep
  ON ep.id = rel.episode_id
WHERE ep.id IS NULL;

SELECT COUNT(*) AS broken_relation_raw_refs
FROM core.nasdaq_halt_episode_event rel
LEFT JOIN raw.nasdaq_trade_halt h
  ON h.id = rel.trade_halt_id
WHERE h.id IS NULL;

-- 3. Duplicate RAW HALT identity V1.2
SELECT COUNT(*) AS duplicate_raw_halt_keys
FROM (
    SELECT
        symbol,
        market,
        halt_date,
        halt_time,
        reason_code,
        COUNT(*) AS n
    FROM raw.nasdaq_trade_halt
    GROUP BY
        symbol,
        market,
        halt_date,
        halt_time,
        reason_code
    HAVING COUNT(*) > 1
) d;

-- 4. Duplicate RESUMPTION identity V1.3
SELECT COUNT(*) AS duplicate_resumption_keys
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
        resumption_trade_time,
        COUNT(*) AS n
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
) d;

-- 5. Semantics: every resumption observation must have at least one reason context
SELECT COUNT(*) AS resumption_rows_without_reason_context
FROM raw.nasdaq_resumption
WHERE reason_code IS NULL
  AND resumption_reason_code IS NULL;

-- 6. Semantics by year
SELECT
    EXTRACT(YEAR FROM resumption_date)::int AS year,
    COUNT(*) AS observations,
    COUNT(*) FILTER (
        WHERE reason_code IS NOT NULL
          AND resumption_reason_code IS NULL
    ) AS halt_context_only,
    COUNT(*) FILTER (
        WHERE reason_code IS NULL
          AND resumption_reason_code IS NOT NULL
    ) AS resumption_context_only,
    COUNT(*) FILTER (
        WHERE reason_code IS NOT NULL
          AND resumption_reason_code IS NOT NULL
    ) AS both_codes,
    COUNT(*) FILTER (
        WHERE reason_code IS NULL
          AND resumption_reason_code IS NULL
    ) AS no_code
FROM raw.nasdaq_resumption
GROUP BY 1
ORDER BY 1;

-- 7. Duplicate CORE identity V1.2
SELECT COUNT(*) AS duplicate_core_keys
FROM (
    SELECT
        symbol,
        market,
        halt_start,
        COUNT(*) AS n
    FROM core.nasdaq_halt_episode
    GROUP BY
        symbol,
        market,
        halt_start
    HAVING COUNT(*) > 1
) d;

-- 8. Duplicate CORE -> RAW relation pairs
SELECT COUNT(*) AS duplicate_relation_pairs
FROM (
    SELECT
        episode_id,
        trade_halt_id,
        COUNT(*) AS n
    FROM core.nasdaq_halt_episode_event
    GROUP BY
        episode_id,
        trade_halt_id
    HAVING COUNT(*) > 1
) d;

-- 9. CORE chronological integrity
SELECT COUNT(*) AS invalid_core_chronology
FROM core.nasdaq_halt_episode
WHERE halt_end IS NOT NULL
  AND halt_end < halt_start;

-- 10. GPUS reference case
SELECT
    ep.id,
    ep.symbol,
    ep.market,
    ep.reason_code,
    ep.halt_start,
    ep.halt_end,
    ep.duration_minutes,
    ep.halt_close_status
FROM core.nasdaq_halt_episode ep
WHERE ep.symbol = 'GPUS'
  AND ep.halt_start = TIMESTAMP '2026-08-14 14:15:13.698';

SELECT
    r.id,
    r.symbol,
    r.market,
    r.halt_date,
    r.halt_time,
    r.reason_code,
    r.resumption_reason_code,
    r.resumption_date,
    r.resumption_quote_time,
    r.resumption_trade_time,
    r.source_file
FROM raw.nasdaq_resumption r
WHERE r.symbol = 'GPUS'
  AND r.halt_date = DATE '2026-08-14'
  AND r.halt_time = TIME '14:15:13.698'
ORDER BY r.id;

-- 11. GPUS must remain HALT H11, never T3 in CORE
SELECT COUNT(*) AS gpus_core_t3_rows
FROM core.nasdaq_halt_episode
WHERE symbol = 'GPUS'
  AND halt_start = TIMESTAMP '2026-08-14 14:15:13.698'
  AND reason_code = 'T3';

-- Expected for checks 2,3,4,5,7,8,9,11: 0.
