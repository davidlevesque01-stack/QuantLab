-- ============================================================
-- QuantLab
-- Migration 016
-- SEC 8-K Warrant Exhibit — match_reason column (SEC-13)
--
-- Purpose:
--   filter_warrant_exhibits (sec_8k_warrant_discovery.py) now matches
--   candidate exhibits on two independent signals: the free-text
--   description ("FORM OF ... WARRANT") and, as a structural fallback,
--   the exhibit type code (EX-4.x, reserved by Item 601(b)(4) of
--   Regulation S-K for "Instruments defining the rights of security
--   holders"). Some filers (e.g. GPUS) never write a descriptive
--   exhibit title ("EXHIBIT 4.1" instead of "FORM OF PRE-FUNDED
--   WARRANT"), making the exhibit_type signal necessary to find their
--   warrants at all — but that signal is also weaker (EX-4.x also
--   covers non-warrant rights instruments, e.g. indentures), so which
--   rule matched must stay auditable per row rather than silently
--   merged into a single boolean.
--
-- Version: 1.0
-- ============================================================

BEGIN;

ALTER TABLE raw.sec_8k_warrant_exhibit
    ADD COLUMN IF NOT EXISTS match_reason VARCHAR(30);

COMMIT;
