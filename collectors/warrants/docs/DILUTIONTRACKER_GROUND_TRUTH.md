# DilutionTracker Ground Truth Reference

**Status:** Reference data only — collected manually by the user from dilutiontracker.com
(2026-09-11) for validation purposes. Not ingested by any collector (see
`WARRANTS_COMPONENT.md`, "No website scraping" — this data was retrieved by a human with
their own account, never scraped automatically).

## Purpose

Ground truth for validating the SEC-native extraction pipeline (SEC-06/09/10/11/12/13) and
future work on convertible notes (CS-01), ATM facilities (CS-02), and two categories not yet
tracked by any issue at all: **equity lines** and **shelf registrations** (see "New categories"
below). Two independent issuers (TNON, GPUS) — cross-referenced against `raw.sec_*` tables to
find real gaps; see `SEC-11`/`SEC-12`/`SEC-13`/`SEC-14` on the GitHub Project for the gaps found
so far.

---

## TNON (Tenon Medical, Inc. — CIK 0001560293)

### SEC-12/SEC-13 real backfill validation (2026-09-11)

Real (non-rollback) run of `run_sec_collection.py --tickers TNON` after implementing SEC-12
(full 8-K history pagination, `fetch_all_8k_filings`) and SEC-13 (EX-4.x exhibit-type fallback,
`match_reason` column). Result: `warrant_exhibits: inserted=5, skipped=20` and
`reverse_splits: inserted=1, skipped=1` — both new discoveries confirmed genuine:

- **SEC-13 confirmed**: two 2022-04-29 exhibits (`EXHIBIT 4.1`/`EXHIBIT 4.2`, `match_reason =
  exhibit_type`) carry no descriptive title at all — invisible to the old description-only
  match, caught only via the EX-4.x structural fallback.
- **SEC-12 confirmed**: a 2023-11-28 "FORM OF WARRANT" exhibit, older than the old 40-most-recent-
  filing cutoff would ever reach, was discovered via full-history pagination.
- **Known false-positive trade-off, not a bug**: two 2026 exhibits ("FORM OF SENIOR CONVERTIBLE
  PROMISSORY NOTES") matched only on `exhibit_type` — EX-4.x also covers non-warrant "instruments
  defining the rights of security holders" (convertible notes included), exactly the
  necessary-but-not-sufficient limitation called out in SEC-13's scope.
- **Pre-migration-016 rows show `match_reason = NULL`**: the 20 exhibits already in
  `raw.sec_8k_warrant_exhibit` from before migration 016 was applied were never retroactively
  backfilled with a `match_reason` (RAW rows are immutable/append-only, and `ON CONFLICT DO
  NOTHING` skips re-insertion of already-known rows) — expected, not a defect.
- **New second reverse split found** (`raw.sec_reverse_split_event`): a **1-for-10** split
  filed 2023-11-07, in addition to the already-known **1-for-35** split filed 2026-08-10
  (SEC-11). This means the cumulative adjustment factor for anything issued **before
  2023-11-07** is **10 × 35 = 350x**, not 35x as previously assumed — directly relevant to
  WRT-06 (retroactive ratio application to `raw.sec_8k_warrant_text_extraction`, still
  deferred). `effective_date` is NULL for this older split: `EFFECTIVE_DATE_PATTERN` in
  `sec_reverse_split_extraction.py` didn't match this filing's phrasing — a known, narrow
  extraction gap (ratio itself was still extracted correctly), not yet fixed.

### Warrants

| Series | Status | Exercise Price | Total Issued | Expiration |
|---|---|---|---|---|
| June 2023 Warrants | EDGAR, Registered | $882.00 | 7,142 | 2028-06-16 |
| February 2024 Warrants | Not Registered | $355.60 | 1,483 | 2029-02-20 |
| September 2024 Warrant | EDGAR, Not Registered | $149.80 | 463 | 2029-09-05 |
| September 2024 Warrant 2 | EDGAR, Registered | $124.25 | 34,938 | 2029-09-16 |
| September 2024 Series A Warrants | EDGAR, Registered | $43.75 | 34,938 | 2029-09-16 |
| September 2024 Series B Warrants | EDGAR, Registered | $43.75 | 34,938 | 2027-09-16 |
| March 2025 Warrant | EDGAR, Registered | $70.00 | 20,957 | 2030-03-25 |
| March 2025 Warrant 2 | EDGAR, Registered | $70.00 | 36,328 | 2030-03-25 |
| March 2025 Series C-1 Warrants | EDGAR, Registered | $43.75 | 69,877 | 2030-03-12 |
| March 2025 Series C-2 Warrants | EDGAR, Registered | $43.75 | 34,938 | 2028-03-12 |
| November 2025 Warrant | EDGAR, Registered | $40.60 | 63,368 | 2028-11-14 |
| June 2026 Common Warrant | Registered | $13.30 | 378,947 | — |
| August 2026 Common Stock Warrant | EDGAR, Registered | $5.02 | 1,058,517 | 2031-08-27 |

Note: several of these (March 2025 Series C-1/C-2, September 2024 Series A/B) share the same
$43.75 price and 34,938-scale quantities — consistent with the ~1-for-35 reverse split already
confirmed in SEC-11 (original issuance quantities in `raw.sec_8k_warrant_text_extraction` are
~35x these post-split figures).

### Convertible Note

| Series | Status | Conversion Price | Shares Issued | Principal | Maturity |
|---|---|---|---|---|---|
| March 2026 Senior Convertible Promissory Note | EDGAR, Not Registered | $28.00 | 153,571 | $4,300,000 | 2026-09-11 |

### Convertible Preferred

| Series | Status | Conversion Price | Shares Issued | Amount Issued |
|---|---|---|---|---|
| February 2024 Convertible Preferred | Not Registered | $355.60 | 10,925 | $3,886,526 |
| September 2024 Preferred Stock | EDGAR, Not Registered | $178.15 | 3,087 | $550,000 |

### ATM (relevant to CS-02)

| Series | Status | Total Capacity | Placement Agent |
|---|---|---|---|
| August 2026 AGP ATM | EDGAR, Registered | $4,397,821 | AGP |
| May 2023 Maxim ATM | EDGAR, Terminated | $6,700,000 | Maxim |

### Equity Line (new category — no existing issue covers this)

| Series | Status | Total Capacity |
|---|---|---|
| July 2023 Lincoln Park SPA | EDGAR, Registered | $10,000,000 |

### Shelf (new category — no existing issue covers this)

| Series | Status | Total Shelf Capacity | Baby Shelf Restriction | Outstanding Shares | Float |
|---|---|---|---|---|---|
| August 2026 Shelf | EDGAR, Registered | $100,000,000 | Yes | 1,264,657 | 1,204,206 |
| May 2023 Shelf | EDGAR, Registered | $50,000,000 | Yes | 1,264,657 | 1,204,206 |

### S-1 Offerings

| Offering | Status | Anticipated Size | Final Size | Final Pricing | Underwriter |
|---|---|---|---|---|---|
| February 2023 S-1 Offering | Withdrawn | $10,000,000 | — | — | Maxim |
| June 2023 S-1 Offering | Priced | $10,000,000 | $5,600,000 | $0.56 | Maxim |
| August 2024 S-1 Offering | Priced | $10,000,000 | $4,500,000 | $3.68 (exercise $3.55) | AGP |
| June 2026 S-1 Offering | Priced | $1,091,874 | $4,200,000 | $0.38 | WallachBeth |

---

## GPUS (CIK 0000896493)

### SEC-12/SEC-13 real backfill validation (2026-09-11)

Real (non-rollback) runs of `run_sec_collection.py --tickers GPUS`, split across two attempts
(the first ran silently and was interrupted mid-`warrant_text_extraction` — see progress-logging
addition above — but had already completed and persisted the `warrants`/`shares_outstanding`/
`warrant_exhibits` steps by then; the second, later run picked up where it left off).

`fetch_all_8k_filings` retrieves GPUS's full 627 8-K filings back to **1998-02-10** (vs. 40
filings back to 2025-10-17 under the old fixed count) — 241 of those match items 1.01/3.02.

Confirmed new discoveries, all previously invisible under the old 40-filing cap and/or
description-only exhibit matching:

- **SEC-13 (EX-4.x fallback) confirmed**, 5 exhibits, all bare `EXHIBIT 4.x` titles with no
  "warrant" text, `match_reason = exhibit_type`:
  - 2023-11-07 (accession 0001214659-23-014653, EX-4.1) — matches the ground truth's "October
    2023 Warrants" / "November 2023 Warrants" era.
  - 2023-10-16 (accession 0001214659-23-013465, EX-4.1 and EX-4.2).
  - 2021-12-22 (accession 0001214659-21-013530, EX-4.1) and 2021-12-16 (accession
    0001214659-21-013284, EX-4.1) — matches "December 2021 Note Class A/B Warrants".
- **SEC-12 (full history) confirmed**, two facts from **2019**, far beyond the old 40-filing
  window:
  - `raw.sec_8k_warrant_text_extraction`: a pre-funded warrant, 12,700,000 shares, filed
    2019-04-01 (accession 0001214659-19-002393).
  - `raw.sec_reverse_split_event`: a **1-for-20** reverse split filed 2019-03-14 — a THIRD
    known split (alongside TNON's two), reinforcing that `effective_date` extraction gaps are a
    recurring pattern on older filings (NULL here too, same as TNON's 2023-11-07 split), not a
    one-off quirk of a single document's phrasing.

### Warrants

Several show `Total Issued: 0` — never exercised, likely expired/cancelled; still worth
discovering for completeness even if numerically inert.

| Series | Status | Exercise Price | Total Issued | Expiration |
|---|---|---|---|---|
| November 2023 Warrants | Not Registered | $437.50 | 79,366 | 2028-11-06 |
| January 2025 Warrant | EDGAR, Not Registered | $29.60 | 32,443 | 2030-01-03 |
| October 2023 Warrants | Not Registered | $803.68 | 10,899 | 2028-10-13 |
| December 2021 Note Class B Warrants | EDGAR, Pending Effect | $131,250.00 | 1 | 2026-12-31 |
| December 2021 Note Class A Warrants | EDGAR, Pending Effect | $3,281,250.00 | 10 | 2026-12-31 |
| October 2020 Note Warrants | Not Registered | $3,399,375.00 | 0 | 2022-03-27 |
| June 2020 Note warrants | EDGAR, Registered | $1,837,500.00 | 0 | 2021-11-25 |
| October 2020 Note Warrants 2 | Not Registered | $2,454,375.00 | 0 | 2022-03-27 |
| Various Feb-May 2020 Note Warrants | EDGAR, Registered | $3,950,625.00 | 2 | 2025-05-27 |
| November 2020 Note Warrants | Not Registered | $1,312,500.00 | 0 | 2025-11-20 |
| August 2020 Esousa Note Warrants | Not Registered | $3,950,625.00 | 0 | 2025-08-05 |
| October 2020 Warrants | Not Registered | $2,887,500.00 | 0 | 2025-10-23 |
| May 2019 Note payable warrants | Not Registered | $0.00 | 0 | 2024-05-20 |
| April 2019 Underwriter Warrants | EDGAR, Registered | $11,550,000.00 | 0 | 2024-04-01 |
| April 2019 Warrants | EDGAR, Registered | $11,550,000.00 | 0 | 2024-04-01 |

### Convertible Notes

| Series | Status | Conversion Price | Shares Issued | Principal | Maturity |
|---|---|---|---|---|---|
| December 2025 Convertible Note | EDGAR, Registered | $1.60 | 7,893,663 | $12,768,000 | 2027-11-30 |
| November 2019 Exchanged Note 2 | Not Registered | $1,903,125.00 | 0 | $935,772 | — |
| November 2019 Exchanged Note | Not Registered | $2,362,500.00 | 0 | $350,000 | — |
| October 2023 Convertible Note (repaid) | Not Registered | $1,291.50 | 13,565 | $17,519,832 | 2028-10-13 |
| July 2019 Convertible promissory note | EDGAR, Registered | $1,575,000.00 | 2 | $3,525,031 | — |
| July 2024 Convertible Note | EDGAR, Registered | $29.75 | 181,176 | $5,390,000 | 2024-10-19 |
| March 2024 Convertible Note | EDGAR, Registered | $61.25 | 32,653 | $2,000,000 | 2024-06-12 |
| September 2023 Convertible Note | EDGAR, Registered | $1,050.00 | 2,095 | $2,200,000 | 2024-09-28 |
| February 2020 8% Convertible note | Not Registered | $3,189,375.00 | 0 | $1,000,000 | 2020-08-05 |
| February 2025 Convertible Note | EDGAR, Not Registered | $20.00 | 96,257 | $1,925,141 | 2025-05-05 |
| March 2025 Convertible Note | EDGAR, Not Registered | $2.00 | 2,096,657 | $4,193,314 | 2025-06-30 |
| March 2025 Convertible Note 2 | EDGAR, Registered | $2.00 | 2,454,705 | $4,909,410 | 2025-12-31 |
| April 2025 Convertible Note | EDGAR, Registered | $2.00 | 825,000 | $1,650,000 | 2025-09-30 |
| April 2025 Convertible Note 2 | EDGAR, Registered | $2.00 | 2,500,000 | $5,000,000 | 2025-09-30 |

---

## New categories not yet covered by any issue

- **Equity Line** (e.g. TNON's Lincoln Park SPA) — a standing agreement to sell shares to an
  investor over time, distinct from an ATM. No data dictionary, no issue.
- **Shelf registration** (e.g. TNON's S-3 shelves) — the overarching registration statement
  that ATM/equity-line/S-1 offerings often draw down against; includes baby-shelf capacity
  restrictions relevant to dilution capacity ceilings. No data dictionary, no issue.
- **S-1 Offerings** (registered direct offerings) — distinct from the private-placement 8-Ks
  SEC-09/10 target; these go through a full S-1/424B prospectus process. Partially adjacent to
  existing SEC-06 (shares outstanding) scope but not explicitly tracked as its own instrument.

Not scoped into any issue yet — flagged here for whenever Capital Structure work resumes beyond
warrants.
