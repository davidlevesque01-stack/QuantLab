-- ============================================================
-- QuantLab
-- Migration 013
-- Add filed_date / form_type to SEC 8-K Warrant Text Extraction (RAW)
--
-- Purpose:
--   raw.sec_8k_warrant_text_extraction (migration 012) was missing
--   filed_date and form_type — the filing date/form were available at
--   extraction time (fetch_8k_filings) but were dropped when building
--   each observation, unlike raw.sec_8k_warrant_exhibit (migration
--   010), which does carry them. Found via manual review of the CSV
--   export: rows had no way to tell when a given warrant term was
--   disclosed.
--
-- IMPORTANT:
--   Additive, non-destructive: adds two nullable columns. Existing
--   rows (captured before this migration) will have NULL filed_date/
--   form_type until backfilled by re-running the collector for the
--   affected CIKs (safe: ON CONFLICT DO NOTHING means a rerun only
--   fills genuinely new observations, so the 9 existing TNON rows must
--   be deleted first for the values to populate on re-collection).
--
-- Version: 1.0
-- ============================================================

BEGIN;

ALTER TABLE raw.sec_8k_warrant_text_extraction
    ADD COLUMN IF NOT EXISTS filed_date DATE;

ALTER TABLE raw.sec_8k_warrant_text_extraction
    ADD COLUMN IF NOT EXISTS form_type VARCHAR(20);

COMMIT;
