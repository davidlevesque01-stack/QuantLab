# Warrants Component — Architecture Decision and Delivery Plan

**Project:** QuantLab  
**Domain:** Capital Structure & Dilution  
**Component:** Warrants  
**Status:** Approved for implementation — source strategy revised (CS-03,
2026-09-18): DilutionTracker dropped as an automated source, DilutionWatch adopted

## Decision

QuantLab will create a dedicated `warrants` component as the first implementation
unit of the broader Capital Structure & Dilution capability.

The component uses a hybrid source strategy:

- SEC EDGAR remains the authoritative legal source, and the sole source for
  per-series warrant/convertible terms (strike, quantity, expiration) — see the
  existing SEC-native extraction pipeline (SEC-06 through SEC-18), which stays
  active, not retired, precisely because DilutionWatch (below) only exposes
  aggregate totals, not per-series terms.
- Nasdaq Trader and FINRA provide security/listing/corporate-action metadata.
- **DilutionWatch** (dilutionwatch.com) is the licensed, structured secondary
  source for aggregate capital-structure metrics (float, institutional ownership,
  cash runway, dilution score, ATM/shelf dollar amounts) — see "DilutionWatch
  pivot" below. It replaces DilutionTracker in this role.
- **Massive** (formerly Polygon.io) supplies premarket/since-close news
  (`GET /v2/reference/news?ticker=X`, includes the Benzinga feed) — the same
  provider already adopted for market data (see
  `docs/backtesting/BACKTESTING_COMPONENT.md`), no separate vendor relationship
  needed for this field.
- **DilutionTracker** (dilutiontracker.com) is retained only as a **manual,
  human-driven reference** for spot-checking (see
  `DILUTIONTRACKER_GROUND_TRUTH.md`) — never an automated ingestion source. See
  "DilutionTracker — corrected status" below for why.

QuantLab preserves its independence from any single secondary source by storing
provenance, linking material records back to SEC filings, and progressively
developing its own primary-source ingestion.

## DilutionTracker — corrected status (CS-03)

An earlier version of this document stated that *"QuantLab has obtained written
confirmation from DilutionTracker regarding retention and continued internal use
of historical data acquired while subscribed."* **This was inaccurate — no such
confirmation exists.** No bootstrap plan, API integration, or written data
agreement with DilutionTracker was ever put in place; `WRT-03`/`WRT-04a`–`WRT-04e`
(the DilutionTracker collector scaffolding) are **superseded** by this pivot — see
`WARRANTS_GITHUB_BACKLOG.md`.

DilutionTracker's own Terms of Service (`dilutiontracker.com/term-of-service`,
read directly, 2026-09-18) settle the question definitively. Section 3 ("Use
License"):

> *"under this license you may not: ... access the Site using any automated
> means, including, without limitation, harvesting bots, robots, spiders, or
> scrapers"* — *"This license shall automatically terminate without refund if you
> violate any of these restrictions."*

Section 9:

> *"Upon termination of your account(s) for any reason, ... all content in your
> account(s) will be deleted."*

DilutionTracker offers **no API and no bulk export** (confirmed directly with
them). Any automated access — scraping the rendered page or replaying the
authenticated app's internal network calls — would violate this license and risk
immediate, unrecoverable loss of the account and everything in it. Principle 5
below ("No website scraping") is kept, now grounded in this concrete finding
rather than a precaution.

## DilutionWatch pivot (CS-03)

DilutionWatch (dilutionwatch.com, operated by Guerilla Finance LLC) is a direct
competitor to DilutionTracker, using the same core method (automated SEC EDGAR
monitoring across ~25 filing types: S-3, 424B, Form 4, 13D/13G/13F, 8-K, 10-K,
10-Q) plus AI analysis. Unlike DilutionTracker, it **sells API access as a
product**: base URL `dilutionwatch.com/api/v1/`, JSON, `X-API-Key` header auth,
credit-metered (1 credit/call, 5 for the full-universe screener), tiers from
$19.95/mo (Basic, UI-only) to $79.95/mo+ (dedicated developer/quant tier).

Confirmed fields (from their published API docs): `symbol`, `company_name`,
`exchange`, `cik`, `market_cap`, `shares_outstanding`, `public_float`,
`short_percent_of_float`, `dilution_score`, `risk_level`,
`share_growth_3yr_pct`, `months_cash_remaining`, `outstanding_warrants`
(aggregate, not per-series), `convertible_shares` (aggregate),
`shelf_capacity_dollars`, `atm_remaining_dollars`, short-interest/FINRA fields,
institutional ownership %, insider transactions, reverse-split ratios, and
fundamentals (revenue, cash, debt, operating/free cash flow).

Their Terms of Service (`dilutionwatch.com/terms.html`, read directly,
2026-09-18) draw the opposite line from DilutionTracker:

- **Website scraping is still prohibited** (Section 11): bots/crawlers/scrapers,
  headless browsers, and "querying API endpoints... at a rate or volume exceeding
  normal human use... consistent with data harvesting" are all disallowed.
- **The paid API itself is the sanctioned access mechanism** — no clause
  prohibits normal programmatic use within purchased credits; that is what the
  product is sold for.
- **Redistribution restriction** (Section 9): API responses, DilutionScores and
  bulk datasets may not be published/resold/redistributed to third parties without
  a separate licensing agreement. QuantLab's internal-only predictive-model use
  fits within this restriction without needing one.
- No clause on data retention after cancellation (more favorable than
  DilutionTracker, which deletes all account content on termination).
- Governing law: Georgia, USA (arbitration, Fulton County) — vs. DilutionTracker's
  Ontario.

**Known gap:** DilutionWatch's aggregate `outstanding_warrants`/`convertible_shares`
do not give per-series strike/quantity/expiration — that granularity still comes
from the SEC-native pipeline (SEC-06 through SEC-18). ITM/resistance-style
calculations (comparing a series' strike to the live share price) are therefore
**computed by QuantLab's own Feature Engine**, from SEC-sourced terms + Massive
market data — never sourced pre-computed from any external vendor. See
`docs/backtesting/BACKTESTING_GITHUB_BACKLOG.md` BT-14.

### Field-by-field source mapping

Derived from `docs/Master_Data_Requirements_Web_Sources_v2.csv` (the original
manual/Excel-based workflow this formalizes):

```text
Field                                    Source
--------------------------------------   --------------------------------------
Float, % institutional                   DilutionWatch (public_float,
                                          institutional ownership %)
Cash duration / cashflow+ / cash burn     DilutionWatch (months_cash_remaining,
                                          fundamentals cash flow)
ATM registered?/amount, Shelf registered? DilutionWatch (atm_remaining_dollars,
                                          shelf_capacity_dollars)
Equity line registered?                  Not yet confirmed on DilutionWatch —
                                          verify directly before relying on it
% short over float                       Benzinga (per the original spec) or
                                          DilutionWatch's short_percent_of_float
Chinese company? / Country               SEC EDGAR (issuer address / 10-K vs.
                                          20-F cover page) — already in our SEC
                                          pipeline, no new vendor
Is there news? / news title               Massive/Polygon news endpoint
                                          (GET /v2/reference/news, Benzinga feed)
                                          — same vendor as market data
Sector of activity                       Not confirmed available via any
                                          documented API from the originally
                                          cited source (TradingView) — needs an
                                          alternative (e.g. SEC SIC code, or a
                                          reference field already on Massive's
                                          ticker-details endpoint); do not assume
                                          TradingView exposes this
36-month HALT history                    Already fully covered by the existing
                                          Nasdaq HALT collector/`core.nasdaq_halt_episode`
                                          — no new work, just a query; daily
                                          refresh scheduling still to be wired up
ITM warrants/notes/preferred, and         Computed by QuantLab's own Feature
"resistance" sums (WEB-005/006/007/       Engine from SEC per-series terms +
013/014/015/016/008)                     core.market_bar_1m — not external data
```

## Architectural principles

### 1. RAW is immutable evidence

Every DilutionWatch API response used by QuantLab should be stored with:

- ticker;
- endpoint;
- retrieval timestamp;
- API version if available;
- complete JSON payload or an equivalent lossless representation.

### 2. CORE is normalized and point-in-time

CORE records must represent historical state, not only the latest state.

### 3. Provenance is first-class data

Important values must identify their origin:

- `DILUTIONWATCH`
- `SEC`
- `NASDAQ`
- `FINRA`
- `MASSIVE`
- `DILUTIONTRACKER` (manual ground-truth entries only — see
  `DILUTIONTRACKER_GROUND_TRUTH.md` — never an automated ingestion row)
- `QUANTLAB_DERIVED`

### 4. SEC remains the source of truth

A DilutionWatch value can be useful and operationally trusted while still being
classified as derived/secondary data. Material discrepancies should trigger review
against the corresponding SEC filing.

### 5. No automated access outside a documented, paid API

Confirmed necessary the hard way (CS-03): DilutionTracker's Terms of Service ban
all automated access with no API alternative, so it is never an ingestion source —
manual, human-driven reference only. DilutionWatch is the opposite case: its
Terms of Service specifically bans scraping the *website* but explicitly sells and
permits programmatic use of its *paid API*, which is what QuantLab uses. The
rule generalizes: never build automated access to a source's rendered pages or
private network calls; only ever integrate a documented, paid-for API/export
mechanism the source itself sanctions.

## Initial logical data model

### `core.security`

Represents securities associated with an issuer. **Coordination note:** the
backtesting component's `core.market_bar_1m` (BT-16) also needs a `security_id`
FK — this table is designed once, shared by both, not duplicated per component.
See `docs/backtesting/BACKTESTING_COMPONENT.md`, "Coordination note".

Candidate security types:

- COMMON_STOCK
- WARRANT
- PREFUNDED_WARRANT
- PREFERRED
- CONVERTIBLE
- UNIT
- RIGHT

### `core.security_snapshot`

Point-in-time aggregate metrics from DilutionWatch, one row per
ticker/refresh-cycle (morning refresh for most fields; every 5 minutes
pre-market for anything price-sensitive per the original spec — though the
price-sensitive fields below are computed by QuantLab itself, not refreshed from
DilutionWatch at that cadence).

Candidate fields:

- `id`
- `security_id`
- `as_of` (point-in-time)
- `public_float`
- `institutional_ownership_pct`
- `months_cash_remaining`
- `cashflow_positive` (bool)
- `cash_burn_per_quarter`
- `dilution_score`, `risk_level`
- `shelf_capacity_dollars`, `atm_remaining_dollars`, `atm_registered` (bool),
  `shelf_registered` (bool)
- `equity_line_registered` (bool) — pending confirmation this field exists on
  DilutionWatch at all; do not assume it does
- `short_percent_of_float`
- `country`, `is_chinese_company` (bool) — sourced from SEC EDGAR, not
  DilutionWatch, but stored alongside since the CSV spec groups them here
- `source_provider` (`DILUTIONWATCH` / `SEC`), `retrieved_at`

### `core.warrant`

Stable identity and relatively invariant warrant attributes.

Candidate fields:

- `id`
- `issuer_id`
- `security_id`
- `warrant_type`
- `issue_date`
- `exercise_start_date`
- `expiration_date`
- `exchange_traded`
- `status`

### `core.warrant_term_history`

Point-in-time terms and quantities.

Candidate fields:

- `id`
- `warrant_id`
- `effective_from`
- `effective_to`
- `exercise_price`
- `exercise_ratio`
- `warrants_outstanding`
- `underlying_shares`
- `cash_exercise`
- `cashless_exercise`
- `redemption_price`
- `redemption_trigger_price`
- `source_type`
- `source_reference`
- `source_date`
- `retrieved_at`

The physical PostgreSQL schema will be finalized after inspection of real API payloads.

## Validation POC

Before full backfill, select 5–10 representative tickers, including difficult cases:

- listed public warrant;
- pre-funded warrant;
- company with multiple warrant series;
- amended/repriced warrant;
- expired/exercised warrant;
- issuer with a recent HALT.

For each ticker:

1. retrieve DilutionWatch aggregate metrics via the API;
2. retain the raw JSON response;
3. locate the referenced SEC filings for the same period;
4. compare float, institutional %, dilution score/risk level against what SEC
   filings and the existing SEC-native pipeline independently support;
5. record discrepancies.

The full backfill starts only after this validation passes. The manual
DilutionTracker ground-truth entries already collected
(`DILUTIONTRACKER_GROUND_TRUTH.md`) remain a useful independent cross-check for
this POC even though DilutionTracker is not an automated source.

## Long-term target

DilutionWatch should become optional, the same way DilutionTracker's role was
originally framed — the goal is still an independent, primary-source-backed
capital-structure model, not permanent dependence on any one secondary vendor.

Target maturity:

```text
SEC + Nasdaq + FINRA + Massive (news)
        |
        v
QuantLab collectors (incl. DilutionWatch API client)
        |
        v
RAW
        |
        v
CORE Capital Structure (core.security, core.security_snapshot, core.warrant,
                         core.warrant_term_history)
        |
        v
Feature Engine (ITM/resistance computed from SEC terms + Massive price -- see
                 docs/backtesting/BACKTESTING_GITHUB_BACKLOG.md BT-14)
        |
        v
Analytics
        |
        v
HALT x dilution x market data
```

DilutionWatch can remain a reconciliation/benchmark source, or the primary
aggregate-metrics source long-term, depending on ongoing value vs. subscription
cost — the same review discipline originally planned for DilutionTracker, now
applied to DilutionWatch instead.

## See also

- `docs/backtesting/BACKTESTING_COMPONENT.md` — market-data provider decision
  (Massive) and the shared `security_id`/`core.security` coordination.
- `docs/data_sources.md` — cross-cutting registry of which provider serves which
  need, across every QuantLab component.
- `docs/Master_Data_Requirements_Web_Sources_v2.csv` — the original field-by-field
  data requirements this pivot was derived from.
- `DILUTIONTRACKER_GROUND_TRUTH.md` — manual reference data, still valid as a
  cross-check, never an automated ingestion source.
