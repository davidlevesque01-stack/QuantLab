-- ============================================================
-- QuantLab
-- Migration 017
-- SEC 8-K Warrant Text Extraction — extraction_method column (SEC-15)
--
-- Purpose:
--   SEC-10's regex extraction (sec_8k_warrant_text_extraction.py) was
--   validated against one real filing and immediately broke on
--   different phrasing from the same issuer (quantity/exercise
--   price/expiration each phrased multiple ways across real filings).
--   SEC-15 adds an LLM-based extraction path
--   (sec_llm_warrant_extraction.py) that reuses this same table, since
--   its output shape (kind/label/share_quantity/exercise_price/
--   expiration_years/raw_snippet) is unchanged — but which method
--   produced a given row must stay auditable, exactly like
--   raw.sec_8k_warrant_exhibit's match_reason column (migration 016).
--
-- IMPORTANT:
--   Existing rows (pre-migration) are all regex-extracted but are NOT
--   backfilled here — RAW rows are immutable/append-only by
--   convention. They show NULL until re-collected.
--
-- Version: 1.0
-- ============================================================

BEGIN;

ALTER TABLE raw.sec_8k_warrant_text_extraction
    ADD COLUMN IF NOT EXISTS extraction_method VARCHAR(10);

ALTER TABLE raw.sec_8k_warrant_text_extraction
    ADD CONSTRAINT chk_sec_8k_warrant_text_extraction_method
        CHECK (extraction_method IS NULL OR extraction_method IN ('regex', 'llm'));

COMMIT;
