# QuantLab Warrants Component

## Purpose

The `warrants` component is the first implementation unit of QuantLab's broader
**Capital Structure & Dilution** domain.

Its goal is to build a point-in-time, auditable history of warrants and related
dilutive instruments so QuantLab can answer questions such as:

- What warrants existed for an issuer at a given date?
- How many warrants were outstanding?
- What were their exercise prices and expiration dates?
- Which warrants were in-the-money at a given market price?
- What potential dilution existed immediately before or after a Nasdaq trading halt?
- Which values came from DilutionTracker and which were validated against SEC filings?

## Source strategy

### Primary / authority sources

- **SEC EDGAR** — contractual terms, quantities, filing history, legal source documents.
- **Nasdaq Trader** — listed-security discovery, symbol and exchange/listing metadata.
- **FINRA** — OTC securities and relevant corporate-action information.

### Structured secondary source

- **DilutionTracker API** — bootstrap, normalization and ongoing validation/enrichment.

DilutionTracker is not the legal source of truth. QuantLab must retain source
provenance and, progressively, validate material terms against SEC EDGAR.

## Commercial strategy

Initial bootstrap:

1. Subscribe to the DilutionTracker plan that permits up to 5,000 unique tickers
   per month, five years of history and bulk/API access.
2. Import the available five-year history.
3. Retain API responses and provenance in PostgreSQL.
4. Validate a representative sample against SEC filings.
5. After bootstrap, reassess whether to:
   - keep a lower DilutionTracker plan;
   - subscribe only periodically for reconciliation; or
   - rely mainly on QuantLab's SEC/Nasdaq/FINRA collectors.

Written confirmation from DilutionTracker permitting retention and continued
internal use of already-obtained historical data after plan downgrade/cancellation
must be preserved in project documentation.

## Processing model

```text
DilutionTracker API ─┐
                     ├─> RAW ─> normalization ─> CORE ─> analytics
SEC EDGAR ───────────┤
Nasdaq Trader ───────┤
FINRA ───────────────┘
```

## Initial scope

The first release focuses on:

- public warrants;
- private warrants where disclosed;
- pre-funded warrants;
- warrant issue date;
- exercise start date;
- expiration date;
- exercise price;
- exercise ratio;
- warrants outstanding;
- underlying shares;
- cash / cashless exercise;
- redemption terms;
- exchange-traded status;
- source provenance;
- historical changes to warrant terms and quantities.

Later phases can add:

- convertible notes;
- preferred securities;
- ATM facilities;
- equity lines;
- shelves;
- S-1/S-3 offerings;
- rights and units.

## Point-in-time requirement

QuantLab must never keep only the latest warrant state.

The model must allow reconstruction of the information known at a historical
date. Example:

```text
2025-01-01  10,000,000 warrants outstanding
2025-06-30   8,400,000 warrants outstanding
2025-12-31   4,200,000 warrants outstanding
2026-03-31           0 warrants outstanding
```

This is required for valid historical analytics and machine-learning features.

## Proposed PostgreSQL layers

### RAW

- `raw.dilutiontracker_response`
- `raw.sec_filing`
- `raw.sec_document`
- later: raw Nasdaq/FINRA security events

### CORE

- `core.security`
- `core.warrant`
- `core.warrant_term_history`
- `core.warrant_source_reference`

### Analytics

Candidate metrics:

- warrant shares outstanding;
- potential dilution shares;
- potential dilution percentage;
- in-the-money warrant shares;
- weighted exercise price;
- nearest expiration;
- capital overhang;
- dilution at selected market-price levels.

## HALT integration

The component is designed to join with the existing Nasdaq HALT domain using
issuer/security identity and point-in-time timestamps.

Future analyses include:

- HALT reason vs. dilution profile;
- post-resumption returns vs. warrant overhang;
- probability of negative post-halt performance when large warrant blocks are ITM;
- interaction of warrant strikes, market price, volume and volatility.

## Implementation sequence

1. Finalize data dictionary.
2. Capture real DilutionTracker API JSON for 5–10 test tickers.
3. Create RAW PostgreSQL tables.
4. Implement `dilutiontracker_collector.py`.
5. Validate test tickers against DilutionTracker UI and SEC.
6. Finalize CORE schema.
7. Run five-year historical backfill.
8. Add integrity/reconciliation checks.
9. Implement SEC collector and filing linkage.
10. Add Nasdaq/FINRA security metadata.
11. Build warrant analytics.
12. Integrate with Nasdaq HALT analytics.
13. Decide the long-term DilutionTracker subscription level.
