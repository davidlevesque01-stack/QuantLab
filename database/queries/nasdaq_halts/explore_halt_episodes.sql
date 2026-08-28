-- ============================================================
-- QuantLab - Nasdaq Halt Episodes
-- Requêtes d'exploration DEV
-- ============================================================

-- Derniers épisodes
SELECT
    symbol,
    reason_code,
    halt_start,
    halt_end,
    duration_minutes,
    halt_close_status
FROM core.nasdaq_halt_episode
ORDER BY halt_start DESC
LIMIT 100;


-- Halts actifs à la clôture
SELECT *
FROM core.nasdaq_halt_episode
WHERE halt_close_status = 'YES'
ORDER BY halt_start DESC;


-- Épisodes multi-jour
SELECT *
FROM core.nasdaq_halt_episode
WHERE halt_close_status = 'MULTI_DAY'
ORDER BY halt_start DESC;

SELECT DISTINCT
    source_file
FROM raw.nasdaq_trade_halt
ORDER BY source_file;
