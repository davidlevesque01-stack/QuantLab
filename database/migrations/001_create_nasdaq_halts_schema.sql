-- Creates:
--   raw.nasdaq_trade_halt
--   core.nasdaq_halt_episode
--
-- Analytics objects are intentionally deferred to a later
-- migration after market-calendar and multi-day halt semantics
-- have been validated against the Python V0.6 baseline.


BEGIN;


-- ============================================================
-- 1. SCHEMAS
-- ============================================================

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS analytics;


-- ============================================================
-- 2. RAW NASDAQ TRADE HALTS
-- ============================================================

CREATE TABLE raw.nasdaq_trade_halt (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    symbol VARCHAR(20) NOT NULL,
    issue_name TEXT,
    market VARCHAR(10) NOT NULL,
    reason_code VARCHAR(20) NOT NULL,

    halt_date DATE NOT NULL,
    halt_time TIME NOT NULL,

    resumption_date DATE,
    resumption_quote_time TIME,
    resumption_trade_time TIME,

    pause_threshold_price NUMERIC(18,6),

    source_file TEXT,

    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_nasdaq_trade_halt_natural_key
        UNIQUE (
            symbol,
            halt_date,
            halt_time,
            reason_code,
            market
        )
);


-- ============================================================
-- 3. RAW INDEXES
-- ============================================================

CREATE INDEX idx_nasdaq_trade_halt_symbol
    ON raw.nasdaq_trade_halt (symbol);

CREATE INDEX idx_nasdaq_trade_halt_date
    ON raw.nasdaq_trade_halt (halt_date);

CREATE INDEX idx_nasdaq_trade_halt_reason
    ON raw.nasdaq_trade_halt (reason_code);

CREATE INDEX idx_nasdaq_trade_halt_symbol_date
    ON raw.nasdaq_trade_halt (symbol, halt_date);


-- ============================================================
-- 4. CORE HALT EPISODES
-- ============================================================

CREATE TABLE core.nasdaq_halt_episode (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    trade_halt_id BIGINT NOT NULL,

    collector_episode_id VARCHAR(20),

    symbol VARCHAR(20) NOT NULL,
    issue_name TEXT,
    market VARCHAR(10),
    reason_code VARCHAR(20),

    halt_start TIMESTAMP NOT NULL,
    halt_end TIMESTAMP,

    duration_minutes NUMERIC(12,3),

    halt_at_close BOOLEAN,

    CONSTRAINT fk_nasdaq_halt_episode_trade_halt
        FOREIGN KEY (trade_halt_id)
        REFERENCES raw.nasdaq_trade_halt (id)
        ON DELETE RESTRICT,

    CONSTRAINT uq_nasdaq_halt_episode_trade_halt
        UNIQUE (trade_halt_id),

    CONSTRAINT chk_nasdaq_halt_duration
        CHECK (
            duration_minutes IS NULL
            OR duration_minutes >= 0
        ),

    CONSTRAINT chk_nasdaq_halt_end
        CHECK (
            halt_end IS NULL
            OR halt_end >= halt_start
        )
);


-- ============================================================
-- 5. CORE INDEXES
-- ============================================================

CREATE INDEX idx_nasdaq_halt_episode_symbol
    ON core.nasdaq_halt_episode (symbol);

CREATE INDEX idx_nasdaq_halt_episode_start
    ON core.nasdaq_halt_episode (halt_start);

CREATE INDEX idx_nasdaq_halt_episode_reason
    ON core.nasdaq_halt_episode (reason_code);

CREATE INDEX idx_nasdaq_halt_episode_symbol_start
    ON core.nasdaq_halt_episode (symbol, halt_start);

COMMIT;
