BEGIN;

ALTER TABLE core.nasdaq_halt_episode
    ADD COLUMN halt_close_status VARCHAR(20);

ALTER TABLE core.nasdaq_halt_episode
    ADD CONSTRAINT chk_nasdaq_halt_close_status
    CHECK (
        halt_close_status IS NULL
        OR halt_close_status IN (
            'YES',
            'NO',
            'UNKNOWN',
            'MULTI_DAY'
        )
    );

ALTER TABLE core.nasdaq_halt_episode
    DROP COLUMN halt_at_close;

COMMIT;
