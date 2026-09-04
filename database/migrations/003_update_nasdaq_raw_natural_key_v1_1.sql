-- ============================================================
-- QuantLab - Nasdaq RAW natural key V1.1
-- ============================================================

ALTER TABLE raw.nasdaq_trade_halt
DROP CONSTRAINT IF EXISTS uq_nasdaq_trade_halt_natural_key;

ALTER TABLE raw.nasdaq_trade_halt
ADD CONSTRAINT uq_nasdaq_trade_halt_natural_key
UNIQUE (
    symbol,
    halt_date,
    halt_time,
    reason_code,
    market,
    resumption_date,
    resumption_trade_time
);