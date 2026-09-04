-- ============================================================
-- QuantLab - Nasdaq CORE natural key V1.1
-- ============================================================

-- V1.0 : un seul RAW par CORE.
-- V1.1 : un CORE peut représenter plusieurs RAW events.
ALTER TABLE core.nasdaq_halt_episode
DROP CONSTRAINT IF EXISTS uq_nasdaq_halt_episode_trade_halt;

-- V1.1 : clé naturelle CORE.
ALTER TABLE core.nasdaq_halt_episode
DROP CONSTRAINT IF EXISTS uq_nasdaq_halt_episode_natural_key;

ALTER TABLE core.nasdaq_halt_episode
ADD CONSTRAINT uq_nasdaq_halt_episode_natural_key
UNIQUE (
    symbol,
    market,
    reason_code,
    halt_start
);
