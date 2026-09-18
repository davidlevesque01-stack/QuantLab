# Warrants Component — Initial GitHub Backlog

Recommended initial issues for the QuantLab GitHub Project.

**Revision note (CS-03, 2026-09-18):** DilutionTracker has no API, no bulk export,
and its Terms of Service ban all automated access outright (confirmed by reading
the ToS directly) — there was never a written retention agreement either, contrary
to an earlier (incorrect) statement in `WARRANTS_COMPONENT.md`. DilutionTracker
stays a manual reference only (`DILUTIONTRACKER_GROUND_TRUTH.md`). **WRT-02,
WRT-03, WRT-04 (and its sub-tickets WRT-04a–e), and WRT-07 are superseded** — see
each ticket below. DilutionWatch (dilutionwatch.com) replaces DilutionTracker's
role via its paid, ToS-sanctioned API; new `CS-0x` tickets below cover that work.
WRT-01/05/06/08/09/10/11 stay valid, retargeted from DilutionTracker to
DilutionWatch/SEC where they referenced it.

## WRT-01 — Define warrant data dictionary

**Goal:** Finalize required fields, semantics, nullability, units and point-in-time rules.

**Acceptance criteria**
- Data dictionary reviewed.
- Stable identity vs. historical terms separated.
- Provenance fields defined.
- Security types enumerated.

## WRT-02 — ~~Capture DilutionTracker API samples~~ SUPERSEDED

**Superseded (CS-03):** no DilutionTracker API exists to sample. See CS-04.

## WRT-03 — ~~Design RAW PostgreSQL schema~~ SUPERSEDED

**Superseded (CS-03):** `raw.dilutiontracker_response` (this ticket's original
target) is replaced by `raw.dilutionwatch_response` — see CS-05.

## WRT-04 — ~~Implement DilutionTracker collector~~ SUPERSEDED (incl. WRT-04a–e)

**Superseded (CS-03):** DilutionTracker's Terms of Service ban all automated
access and no API/export exists — confirmed directly, not merely assumed. The
generic HTTP client / persistence / wiring work already done under WRT-04a–d is
not wasted: the same shape (client → writer → collector) is reused for
DilutionWatch under CS-06, pointed at a real, ToS-sanctioned endpoint this time.

## WRT-05 — SEC validation POC (retargeted)

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

## WRT-07 — ~~Five-year historical bootstrap~~ SUPERSEDED

**Superseded (CS-03):** the licensed five-year DilutionTracker plan this ticket
assumed was never actually activated (no written agreement exists). Reframed as
CS-07 against DilutionWatch, scoped to whatever history their API actually
exposes (their score/filings endpoints recalculate from current SEC EDGAR data,
not necessarily a deep historical archive — confirm actual depth before assuming
five years).

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

## WRT-12 — ~~DilutionTracker subscription review~~ SUPERSEDED

**Superseded (CS-03):** retargeted as CS-08, reviewing the DilutionWatch API tier
instead once real usage data exists.

## CS-03 — Correct DilutionTracker ToS assumption; document DilutionWatch pivot

**Goal:** This documentation revision itself (tracked as GitHub issue CS-03).

**Acceptance criteria**
- `WARRANTS_COMPONENT.md` no longer claims a written DilutionTracker retention
  confirmation that doesn't exist.
- DilutionTracker ToS findings (no automated access, no API) and DilutionWatch ToS
  findings (paid API sanctioned, website scraping still banned) documented with
  exact clause quotes.
- Field-by-field mapping from `docs/Master_Data_Requirements_Web_Sources_v2.csv`
  documented (this file).
- WRT-02/03/04(a–e)/07/12 marked superseded in this file.

## CS-04 — DilutionWatch API client

**Goal:** Generic authenticated HTTP client for `dilutionwatch.com/api/v1/`.

**Acceptance criteria**
- Config via environment variables (`QUANTLAB_DILUTIONWATCH_API_KEY` or similar),
  never committed.
- `X-API-Key` header auth, credit-usage/status endpoint checked before bulk calls.
- Stays within purchased credit limits — no retry storm that burns credits on
  transient failures.

## CS-05 — Design `raw.dilutionwatch_response` schema

**Goal:** Persist DilutionWatch API responses losslessly and idempotently.

**Acceptance criteria**
- Raw response table migration created (next free migration number).
- Duplicate/replay behavior documented (`ON CONFLICT DO NOTHING`, immutable RAW).
- Advisory lock objid registered in `docs/database.md` §21.

## CS-06 — Implement DilutionWatch collector

**Goal:** Wire CS-04's client + CS-05's schema into a runnable collector,
following the same shape already built (then unused) for DilutionTracker under
WRT-04a–d.

**Acceptance criteria**
- `collect_ticker()`-style entry point, config-driven.
- RAW write succeeds; tests pass (including a rolled-back live-DB test, per the
  project's established pattern).

## CS-07 — Design `core.security` / `core.security_snapshot` shared schema

**Goal:** One shared `core.security` table (coordinated with
`docs/backtesting/BACKTESTING_GITHUB_BACKLOG.md` BT-16's `security_id` need, not
duplicated), plus `core.security_snapshot` for DilutionWatch's point-in-time
aggregate metrics.

**Acceptance criteria**
- Migration created; both the warrants component and `core.market_bar_1m`
  reference the same `core.security.id`.
- `core.security_snapshot` fields match the "Initial logical data model" section
  of `WARRANTS_COMPONENT.md`.
- Historical reconstruction (point-in-time `as_of`) supported.

## CS-08 — DilutionWatch subscription tier review

**Goal:** After real usage, quantify credit consumption and decide which paid
tier fits (Basic/Premium/API, or a higher API allotment).
