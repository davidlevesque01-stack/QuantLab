SELECT
    symbol,
    reason_code,
    halt_start,
    halt_end,
    duration_minutes,
    halt_close_status
FROM core.nasdaq_halt_episode
WHERE symbol = 'QVCG'
  AND halt_start >= TIMESTAMP '2026-08-07 00:00:00'
  AND halt_start <  TIMESTAMP '2026-08-08 00:00:00'
ORDER BY halt_start DESC;
