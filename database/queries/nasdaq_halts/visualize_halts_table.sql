SELECT
    id,
    trade_halt_id,
    collector_episode_id,
    symbol,
    issue_name,
    market,
    reason_code,
    halt_start,
    halt_end,
    duration_minutes,
    halt_close_status
FROM core.nasdaq_halt_episode
ORDER BY halt_start DESC
LIMIT 1000;
