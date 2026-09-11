# Warrants Component — Initial GitHub Backlog

Recommended initial issues for the QuantLab GitHub Project.

## WRT-01 — Define warrant data dictionary

**Goal:** Finalize required fields, semantics, nullability, units and point-in-time rules.

**Acceptance criteria**
- Data dictionary reviewed.
- Stable identity vs. historical terms separated.
- Provenance fields defined.
- Security types enumerated.

## WRT-02 — Capture DilutionTracker API samples

**Goal:** Retrieve and archive real API JSON for 5–10 representative tickers.

**Acceptance criteria**
- Samples include multiple warrant patterns.
- No credentials committed.
- Endpoints and retrieval timestamps documented.

## WRT-03 — Design RAW PostgreSQL schema

**Goal:** Persist API payloads losslessly and idempotently.

**Acceptance criteria**
- Raw response table migration created.
- Duplicate/replay behavior documented.
- Retrieval metadata retained.

## WRT-04 — Implement DilutionTracker collector

**Goal:** Add authenticated API ingestion.

**Acceptance criteria**
- Config via environment variables.
- Token never logged or committed.
- Timeouts/retries handled.
- RAW write succeeds.
- Tests pass.

## WRT-05 — SEC validation POC

**Goal:** Validate warrant quantity, strike, expiration and type against SEC filings.

**Acceptance criteria**
- 5–10 tickers reviewed.
- Filing accession/reference retained.
- Discrepancies classified.

## WRT-06 — Design CORE warrant schema

**Goal:** Create point-in-time warrant entities and term history.

**Acceptance criteria**
- Migrations reviewed.
- Historical reconstruction supported.
- Provenance first-class.

## WRT-07 — Five-year historical bootstrap

**Goal:** Import the licensed historical universe.

**Acceptance criteria**
- Complete import report produced.
- Counts by ticker/security type recorded.
- Failures retryable.
- Integrity checks pass.

## WRT-08 — Build reconciliation controls

**Goal:** Detect source conflicts and suspicious changes.

**Acceptance criteria**
- Quantity/strike/expiration discrepancies surfaced.
- Reconciliation report reproducible.

## WRT-09 — Add Nasdaq/FINRA enrichment

**Goal:** Enrich listing/security metadata from primary market sources.

## WRT-10 — Implement warrant analytics

**Goal:** Calculate initial dilution and warrant-overhang metrics.

## WRT-11 — Integrate warrants with Nasdaq HALT analytics

**Goal:** Join point-in-time warrant state to HALT episodes without look-ahead bias.

## WRT-12 — DilutionTracker subscription review

**Goal:** After bootstrap, quantify ongoing value and decide Business/Pro/Starter/periodic/no subscription.
