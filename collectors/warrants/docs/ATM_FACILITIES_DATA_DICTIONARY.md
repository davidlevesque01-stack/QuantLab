# ATM Facilities — Data Dictionary (CS-02)

**Status:** Data dictionary only — no code, no migration, no collector in this issue.

## Purpose

Define what an at-the-market (ATM) equity offering facility record needs
to contain and where each field can realistically be sourced, following
the same source-strategy pattern already validated for warrants
(`WARRANTS_COMPONENT.md`, SEC-05/06/09) and convertible notes (CS-01,
`CONVERTIBLE_NOTES_DATA_DICTIONARY.md`).

## Verified SEC EDGAR XBRL coverage: none ATM-specific

Checked directly against SEC's XBRL frames API (same verification
discipline as CS-01 and SEC-06 — no field below was assumed without
confirming real reporting entities):

| Concept (`us-gaap:`) | Unit | Entities reporting (CY2025Q4) | Caveat |
|---|---|---|---|
| `ProceedsFromIssuanceOfCommonStock` | USD | 76 | Generic — captures any common stock issuance, not specifically ATM |
| `StockIssuedDuringPeriodSharesNewIssues` | shares | 41 | Generic — same caveat |
| `SaleOfStockNumberOfSharesIssuedInTransaction` | shares | 10 | Generic sale-of-stock concept, not ATM-specific |
| `SaleOfStockConsiderationReceivedPerTransaction` | USD | 1 | Essentially unused |

**Conclusion: there is no dedicated XBRL concept for an ATM facility.**
Unlike warrants (`ClassOfWarrantOrRight*`) or convertible notes
(`DebtInstrumentConvertibleConversionPrice1`), nothing in the us-gaap
taxonomy distinguishes "shares issued under an ATM program" from any
other equity issuance (private placement, registered direct offering,
etc.). An issuer's aggregate share-issuance facts cannot be attributed
to an ATM facility from structured data alone.

## Primary discovery path: text, not XBRL

ATM programs are announced through a predictable pair of filings:

1. **8-K** (typically items 1.01 and/or 8.01) announcing entry into a
   Sales Agreement / Equity Distribution Agreement / At-The-Market
   Offering Agreement with a sales agent (e.g. a placement bank).
2. **Form 424B5** (prospectus supplement) registering the shares to be
   sold under the program, which contains the actual facility size
   (aggregate offering amount) and sales agent identity in its text.

This is the exact same discovery shape SEC-09 already built for
warrants — 8-K item filtering + exhibit/document description matching —
just with a different keyword set. `sec_8k_warrant_discovery.py`'s
`WARRANT_DESCRIPTION_PATTERN` (`/warrant/i`) would need an ATM-specific
equivalent (candidate pattern: `/at.the.market|sales agreement|equity distribution agreement/i`)
plus a distinct form-type filter that includes `424B5`, not just 8-K
exhibits. Not built yet — candidate follow-up once this domain gets its
own collection work, likely reusable infrastructure rather than a
one-off script given the structural overlap with SEC-09.

## Candidate CORE data model

Point-in-time shape, mirroring `core.warrant` / `core.warrant_term_history`:

### `core.atm_facility`

Stable identity:

- `id`
- `issuer_id` (-> `core.security`)
- `agreement_date`
- `sales_agent`
- `status` (active / terminated / fully utilized)
- `source_type` (`SEC_8K` / `SEC_424B5` / `DILUTIONTRACKER` / `QUANTLAB_DERIVED`)
- `source_reference`

### `core.atm_facility_usage_history`

Point-in-time cumulative usage — the one place structured data can help,
since `ProceedsFromIssuanceOfCommonStock` / `StockIssuedDuringPeriodSharesNewIssues`
can serve as an imperfect proxy for period-over-period equity raised,
even without being ATM-attributable on their own:

- `id`
- `atm_facility_id`
- `effective_from` / `effective_to`
- `aggregate_offering_amount` (facility ceiling, from the 424B5 text)
- `cumulative_shares_sold`
- `cumulative_proceeds`
- `source_type`
- `source_reference`
- `source_date`
- `retrieved_at`

## Not in scope here

- No `raw.*` table, no migration, no collector — this issue is the
  dictionary only, matching its Backlog description.
- No decision yet on whether ATM facilities get their own `collectors/`
  component, extend the warrants one, or share infrastructure with a
  future generalized "8-K + prospectus discovery" module covering
  warrants, convertible notes, and ATM facilities together.
