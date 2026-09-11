# Convertible Notes — Data Dictionary (CS-01)

**Status:** Data dictionary only — no code, no migration, no collector in this issue.

## Purpose

Define what a convertible note record needs to contain and where each field
can realistically be sourced, following the same source-strategy pattern
already validated for warrants (`WARRANTS_COMPONENT.md`, SEC-05/06/09):
SEC EDGAR as the primary/authoritative source, structured where XBRL
tagging exists, free-text filing exhibits as the fallback where it
doesn't.

## Verified SEC EDGAR XBRL coverage

Checked directly against SEC's XBRL frames API (`CY2025Q4I`, i.e. instant
facts for the quarter ending 2025-Q4) rather than assumed — the same
verification discipline used for `ClassOfWarrantOrRight*` before scoping
SEC-06.

| Concept (`us-gaap:`) | Unit | Entities reporting | What it represents |
|---|---|---|---|
| `DebtInstrumentFaceAmount` | USD | 274 | Principal amount of a debt instrument (convertible or not) |
| `ConvertibleNotesPayableCurrent` | USD | 228 | Aggregate convertible notes payable, current portion — balance-sheet total, not per-note |
| `ConvertibleNotesPayable` | USD | 143 | Aggregate convertible notes payable, non-current — same caveat |
| `DebtInstrumentInterestRateStatedPercentage` | pure | 100 | Stated interest rate of a debt instrument |
| `DebtInstrumentConvertibleConversionPrice1` | USD/shares | 55 | Conversion price per share — the closest analogue to a warrant's exercise price |
| `DebtConversionConvertedInstrumentSharesIssued1` | shares | 5 | Shares actually issued upon a conversion event (rare — only fires when a conversion happened in the period) |

**Key difference from warrants**: convertible notes are conventionally
expressed as a **conversion price** (`DebtInstrumentConvertibleConversionPrice1`),
not a conversion ratio — there is no `DebtInstrumentConvertibleConversionRatio1`
concept (confirmed 404 on the frames API). Warrants use a ratio-oriented
model (`ClassOfWarrantOrRightNumberOfSecuritiesCalledByEachWarrantOrRight`);
convertible notes don't need one, since the number of shares on conversion
is principal ÷ conversion price.

**Coverage caveat, same as warrants**: `ConvertibleNotesPayable(Current)`
are balance-sheet aggregates (one number per issuer per period), not a
per-instrument breakdown when an issuer has multiple outstanding notes
with different terms. `DebtInstrumentConvertibleConversionPrice1`, tagged
by only 55 issuers, is far from universal — most of the HALT-adjacent
microcap universe this project targets will not tag it at all.

## Expected gap: 8-K exhibits

Convertible notes are, like warrants, very commonly issued through a
private placement announced via 8-K (items 1.01/3.02), with the note's
actual terms living in an exhibit such as "FORM OF CONVERTIBLE
PROMISSORY NOTE" or "FORM OF SECURED CONVERTIBLE NOTE" — never reaching
footnote-level XBRL at issuance, exactly the gap SEC-09 was built to
surface for warrants. `sec_8k_warrant_discovery.py`'s exhibit-description
matching (`WARRANT_DESCRIPTION_PATTERN`) would need a convertible-note
equivalent (e.g. matching `/convertible|promissory note/i`) to reuse the
same discovery mechanism — not built yet, candidate follow-up once this
domain gets its own collection work.

## Candidate CORE data model

Point-in-time shape, mirroring `core.warrant` / `core.warrant_term_history`
from `WARRANTS_COMPONENT.md` (not created — deferred behind WRT-06, same
as warrants):

### `core.convertible_note`

Stable identity:

- `id`
- `issuer_id` (-> `core.security`)
- `issue_date`
- `maturity_date`
- `status`

### `core.convertible_note_term_history`

Point-in-time terms:

- `id`
- `convertible_note_id`
- `effective_from` / `effective_to`
- `principal_amount` (`DebtInstrumentFaceAmount` where tagged)
- `interest_rate` (`DebtInstrumentInterestRateStatedPercentage` where tagged)
- `conversion_price` (`DebtInstrumentConvertibleConversionPrice1` where tagged)
- `source_type` (`SEC_XBRL` / `SEC_EXHIBIT` / `DILUTIONTRACKER` / `QUANTLAB_DERIVED`)
- `source_reference`
- `source_date`
- `retrieved_at`

## Not in scope here

- No `raw.*` table, no migration, no collector — this issue is the
  dictionary only, matching its Backlog description.
- No decision yet on whether convertible notes get their own
  `collectors/` component or extend the existing warrants one, the way
  shares outstanding (SEC-01/02) did.
