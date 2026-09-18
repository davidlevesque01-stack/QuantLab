# Backtesting Component — Architecture Decision and Delivery Plan

**Project:** QuantLab
**Domain:** Historical Intraday Predictive Replay
**Component:** Backtesting
**Status:** Approved for implementation (vertical slice first; primary market-data
provider decided — see "Provider decision (v2)" below)

## Decision

QuantLab will build a **Historical Intraday Predictive Replay Engine**: given a
ticker and a historical trading day, the engine replays the market chronologically,
minute by minute, exactly as it would have been observed at each simulated instant,
and lets predictive models be evaluated against what actually happened afterward.

The MVP validates **model correctness**, not execution realism. Order simulation,
position sizing, spread, slippage, commissions and P&L are explicitly out of scope
until the model layer is statistically validated (a later Trading Simulation phase).

Two cross-cutting decisions frame delivery:

- **Sequencing:** a vertical slice first. Build the full chain (Simulated Clock →
  MarketContext → Aggregation → a couple of features → viewer) end-to-end against a
  small local fixture (one ticker, one day) before spending on a paid intraday data
  provider. This validates the point-in-time logic and the interactive UX cheaply.
- **Intraday data provider:** decided — **Massive (formerly Polygon.io)**, US Stocks
  SIP `minute_aggs_v1`, is the primary consolidated market-data source for the MVP
  (see "Provider decision (v2)" below). Databento remains a future option for
  venue-specific microstructure research, not the MVP path. Nothing downstream
  (Feature Engine, models, viewer) depends on which provider is picked — that
  independence is exactly what makes revising this decision cheap.

## Provider decision (v2)

Massive rebranded from Polygon.io on 2025-10-30; APIs, accounts and data products
continued through the rebrand. The MVP primary historical input is the daily
`us_stocks_sip/minute_aggs_v1` flat file: one-minute OHLCV across all U.S. equities,
consolidated from CTA Tapes A/B + UTP Tape C (major exchanges, FINRA facilities and
dark-pool reporting) — a **bulk, whole-market daily file**, not a per-ticker API
call. `trades_v1`/`quotes_v1` remain optional, for later validation (Golden Market
Day reconstruction, §"Validation strategy with Massive" below) or tick-level
research, not the MVP path.

```text
Need                              Selected source              MVP status
Consolidated U.S. OHLCV 1M        Massive minute_aggs_v1        Primary
Consolidated U.S. trades          Massive trades_v1              Optional validation
Top-of-book quotes / NBBO         Massive quotes_v1               Later
Nasdaq HALTs / resumptions        Existing Nasdaq HALT engine    Primary specialized
SEC filings / regulatory data     SEC EDGAR                      Primary specialized
Venue microstructure / order book Direct feeds / Databento        Future optional
```

Why Massive for the MVP: matches the required *consolidated* U.S. view rather than a
Nasdaq-only venue view; ships as downloadable daily flat files (fits the immutable
RAW archive pattern, avoids thousands of per-symbol calls); documents minute
aggregates back to 2003-09-10 (plan-dependent); keeps a validation path open via its
own `trades_v1`. No fournisseur externe (Massive or otherwise) is ever treated as
"100% identical to Nasdaq" on marketing promise alone — QuantLab owns its own
validation layer and measures the gap explicitly (§"Validation strategy" below).
Massive flat files are documented as **unadjusted**; corporate-action adjustment is
therefore an explicit, versioned QuantLab transformation, never assumed from the raw
values.

### Diagrams

The functional pipeline (Sources → Adapters → Raw Store → Data Quality → Canonical
Model → Historical Data API → Replay Engine → MarketContext → Aggregation → Feature
Engine → Predictive/Strategy layers → Batch/Viewer → Outcome/Evaluation → Experiment
Store) has an editable visual source of truth:

```text
docs/backtesting/QuantLab_US_Equities_Functional_Architecture_v2.drawio   (source of truth, edit in draw.io)
docs/backtesting/QuantLab_US_Equities_Functional_Architecture_v2.svg     (export, embed in Markdown/PRs)
```

Regenerate the `.svg` from the `.drawio` file whenever the source diagram changes —
the ASCII diagrams in this document are kept in sync by hand as a text-searchable,
diffable summary, but the `.drawio`/`.svg` pair is authoritative for the visual
layout.

## Architectural principles

### 1. No knowledge of the future

If `SIMULATED TIME = 10:17`, every read available to the Feature Engine must satisfy
`information_timestamp <= 10:17`. This is enforced structurally by `MarketContext`,
not by convention — a request for data after the simulated clock must be technically
rejected, not merely discouraged. This applies to market bars, HALTs, SEC filings,
warrants/convertibles and any other historical data a model consumes.

### 2. Closed bars vs. in-progress bars

At `10:17`, a 5-minute bar covering `10:15 -> 10:19:59` is not finished. The engine
must never expose its final `high`/`low`/`close`/`volume` before that bar closes.
The Aggregation Engine explicitly distinguishes Closed Bar and In-Progress Bar states.

### 3. One Replay Engine, two modes

Interactive Replay (driven by the viewer, for understanding *why* a model reacted at
a given instant) and Batch Replay (driven by orchestration, for running thousands of
ticker/day scenarios) share the same engine. No parallel implementation.

### 4. RAW is immutable, CORE is enriched, analytics is read-only

Same discipline as the Nasdaq HALT and warrants pipelines: source market data is
never modified in place; enrichment is additive at CORE; the replay/feature/model
layers read the database but do not mutate market data. The exception is the
Prediction Log, which writes canonical backtest results to CORE (these are business
records, not derived analytics views — consistent with the `analytics` PostgreSQL
schema not yet being populated anywhere in QuantLab).

### 5. Provider independence

```text
MassiveAdapter (primary) ──┐
StubAdapter/CSV (tests)  ──┼──► QuantLab Canonical Model (raw/core.market_bar_1m)
DatabentoAdapter (future)──┘
```

A change of intraday provider must never require changing the Feature Engine or any
model. The canonical table carries provenance metadata (`source_provider`,
`source_dataset`, `dataset_version`) but never provider-specific business logic.

### 6. Scientific reproducibility

Every backtest run records dataset version, feature version, model id/version,
parameters, ticker universe, period and Git commit, so any result can be traced back
to the exact code and data that produced it.

### 7. Source Adapter and Historical Data API are not the same component

The functional reference diagram draws these as two distinct boxes, and BT-01's
first draft blurred that line: `QuantLabAdapter.fetch_bars(ticker, trading_day)` was
built as a direct fixture-to-Replay bridge, bypassing PostgreSQL entirely. That
shape does not survive contact with Massive's real distribution model — one
`minute_aggs_v1` flat file per day covers the **entire U.S. equity market**, not one
ticker, so a real ingestion adapter must download and persist a whole day's rows in
one pass, never answer a live per-ticker request.

```text
SOURCE ADAPTER                          HISTORICAL DATA API
(ingestion: external -> RAW/CORE)       (replay-time read: CORE -> Replay Engine)

MassiveAdapter: download+parse the      MarketBarSource (analytics/replay/):
day's flat file, call                   read-only, mirrors
persist_market_bars() for every row     analytics/nasdaq_halts/core_source.py,
in it (or the tracked ticker subset)    consumed by the Replay Engine — never
                                         calls an adapter directly
CSVAdapter: same interface, seeded
from a fixture for tests/dev
```

The Replay Engine must depend on the Historical Data API, never on a Source
Adapter. This reclassifies BT-01/BT-05's boundary (see
`BACKTESTING_GITHUB_BACKLOG.md`) but does not invalidate anything already merged —
`collectors/market_data/src/csv_adapter.py` becomes the ingestion-side stub adapter
it always functionally was; a new `analytics/replay/market_bar_source.py` becomes
the actual read path the Replay Engine calls.

## Initial logical data model (candidate — finalized per chantier)

### `raw.market_bar_1m` / `core.market_bar_1m`

One row per ticker/minute. Only 1-minute OHLCV is persisted; every larger timeframe
(2m/5m/15m/30m/1h/daily) is computed on demand by the Aggregation Engine, never
depended upon from a provider's own aggregation.

BT-01 shipped a first cut: `ticker`, `market`, `bar_start` (naive, Nasdaq-local wall
clock per BT-00's `NASDAQ_TZ`), `open`, `high`, `low`, `close`, `volume`, `source`.
Migration `018` is already applied to DEV and is never edited retroactively.

The Massive provider decision needs richer fields than that first cut — a **new
additive migration** (next free number at implementation time) adds:

```text
security_id          -- FK into core.security (see coordination note below),
                         not a bare ticker string
market_scope         -- 'CONSOLIDATED_US' for SIP-consolidated data; the legacy
                         `market` column (venue letter code, e.g. Nasdaq HALT's
                         'A'/'Q') becomes nullable/optional, meaningful only for a
                         future venue-specific direct feed, not for SIP bars which
                         have no single venue per bar
session              -- pre-market / regular / after-hours, computed at ingestion
                         from shared/calendar/trading_calendar.get_session_bounds()
transaction_count    -- optional, when the source reports it
source_provider      -- e.g. 'MASSIVE'
source_dataset       -- e.g. 'us_stocks_sip/minute_aggs_v1'
dataset_version
ingestion_run_id
```

`market` stays additive/nullable rather than removed — no retroactive rewrite of an
applied migration, consistent with the project's migration discipline.

**Coordination note — `core.security`:** `security_id` should not be invented
twice. The capital-structure/warrants component already anticipates a
`core.security` table (see `collectors/warrants/docs/WARRANTS_COMPONENT.md`), and
the DilutionWatch pivot (see that same document, "DilutionWatch pivot") needs it
too — one shared table, designed once, referenced by both `core.market_bar_1m` and
the capital-structure tables, not a market-data-specific reinvention.

**Raw archive provenance:** Massive flat files are retained unchanged as the
immutable RAW artifact, with a **checksum** (e.g. SHA-256) recorded alongside
provenance metadata (retrieval timestamp, dataset version) — the same discipline
`raw.nasdaq_trade_halt` applies to XML source files, extended with an integrity
hash because a single flat file now represents the whole market for one day, not
one ticker's events.

### `reference.trading_day` / `reference.exchange`

Backing store for the official market calendar (pre-market 04:00 / regular
09:30-16:00 / after-hours 20:00), closing the calendar debt already noted in
`docs/architecture.md` (§22) rather than deferring it again. `shared/calendar/trading_calendar.py`
becomes a thin loader over this reference data rather than the sole source of truth.

### `core.backtest_run` / `core.backtest_prediction` / `core.backtest_prediction_evaluation`

Canonical prediction ledger: one row per emitted prediction (ticker, timestamp,
price, model id/version, probability, target, horizon), enriched post-hoc with the
realized outcome (max return, max price, time to target, min return, SUCCESS/FAILURE)
once the replay has advanced past the prediction horizon.

The physical PostgreSQL schema is finalized per chantier (BT-01, BT-07), not upfront,
following the same discipline as the warrants component. Migration numbers are taken
from whatever is next-free at implementation time, not reserved in advance — check
`database/migrations/` before assuming a number is free (018 is the latest applied
as of this revision).

## Validation strategy with Massive

Two complementary levels, per the Massive architecture options review:

```text
Level 1 — Source/RAW validation (BT-12)
  minute_aggs_v1 checked for integrity, continuity, timestamps, OHLC consistency,
  compared against independent reference days.

Level 2 — Aggregation cross-check
  Massive trades_v1
        |
        v
  QuantLab aggregation rules
        |
        v
  Calculated 1M OHLCV
        |
        +---- compare ---- Massive minute_aggs_v1
        |
        +---- compare ---- independent visual/reference source (TradingView, etc.)
```

Selected Golden Market Days are reconstructed from `trades_v1` to validate
QuantLab's own aggregation logic against Massive's pre-computed minute aggregates,
documenting trade-eligibility/sale-condition rule differences when they arise,
rather than assuming either side is automatically correct.

## Architecture options (revised)

| Option | Description | Position |
|---|---|---|
| A — PostgreSQL-centric | Massive flat files → RAW → PostgreSQL → Replay | **RECOMMENDED MVP** |
| B — PostgreSQL + Parquet | Add canonical Parquet for large multi-year batch analytics | Recommended evolution once scale justifies it — does not change the Historical Data API's interface |
| C — Event/tick architecture | `trades_v1`/`quotes_v1` or direct venue feeds → event store → event replay → dynamic bars/features | Future specialized research (spread/liquidity/execution realism), not required for the MVP |
| D — External backtesting engine | QuantLab canonical data feeds LEAN or another execution engine | Potential Phase 2 complement for execution simulation — never replaces the QuantLab Replay Engine, MarketContext, or Feature Engine |

## Validation plan (vertical slice, not full backfill)

Before any real provider integration:

1. Pick one reference ticker/day already known in the repo (GPUS, 2026-08-14 — an
   existing validated Nasdaq HALT reference case) and build a small fixture CSV.
2. Prove the Aggregation Engine is 100% deterministic against that fixture.
3. Prove `MarketContext(as_of=...)` technically rejects any read past the simulated
   clock (the single most important test in this component).
4. Prove one or two simple features (VWAP, RVOL) match a golden dataset.
5. Wire the viewer against the fixture, then the real `MassiveAdapter` (moved
   earlier in the sequence now that the provider is decided — see
   `BACKTESTING_GITHUB_BACKLOG.md`), then a real model.

Full historical backfill (the entire ticker universe, multi-year) stays deferred
past this point — the provider itself is no longer an open question.

## Long-term target

Full functional pipeline (see the `.drawio`/`.svg` diagrams for the visual layout):

```text
EXTERNAL SOURCES
  Massive (formerly Polygon.io) -- US Stocks SIP, minute_aggs_v1 [MVP]
  Nasdaq HALTs / SEC EDGAR -- specialized, existing pipelines
  DilutionWatch -- capital-structure/dilution data (see WARRANTS_COMPONENT.md)
  Databento / direct venue feeds -- future, venue microstructure
        |
        v
SOURCE ADAPTERS  (collectors/market_data, collectors/warrants)
        |
        v
RAW DATA STORE  (immutable, provenance + checksum)
        |
        v
DATA QUALITY  (integrity, gaps, duplicates, timestamps, independent reference checks)
        |
        v
CANONICAL DATA MODEL  (PostgreSQL: reference / core -- core.market_bar_1m,
                        core.security, core.security_snapshot)
        |
        v
HISTORICAL DATA API  (analytics/replay -- read-only, never the Source Adapter)
        |
        v
REPLAY ENGINE  (Simulated Clock)
        |
        v
MARKET CONTEXT  (information available at simulated time)
        |
        v
TIME AGGREGATION  (1M -> 2M / 5M / 15M / 30M / 1H / D)
        |
        v
FEATURE ENGINE  (market / halts / warrants / convertibles / fundamentals / sec)
        |
        v
FEATURE SNAPSHOT  (versioned indicators at time T)
        |
        v
PREDICTIVE MODEL  ->  STRATEGY MODEL (optional)  ->  PREDICTION LOG
        |
        v
BATCH BACKTEST (orchestration/jobs)  <-------------------->  INTERACTIVE VIEWER (ui/replay)
        |                                                          ^
        v                                                          |
OUTCOME ENGINE -> EVALUATION -> EXPERIMENT STORE  ----- review/explain --------┘
```

Halts features reuse `analytics/nasdaq_halts` as-is. Warrants/convertibles/security
features depend on `core.security` / `core.security_snapshot` from the capital
structure component (see `collectors/warrants/docs/WARRANTS_COMPONENT.md`, updated
for the DilutionWatch pivot) — this dependency is coordinated explicitly, not
duplicated, and shares its `security_id` with `core.market_bar_1m` (see the
coordination note above).

QuantConnect LEAN and VectorBT remain optional, future, complementary tools for the
later Trading Simulation phase — QuantLab is not built around either (Option D
above).

## See also

- `docs/data_sources.md` — cross-cutting registry of which provider serves which
  need, across every QuantLab component (not just backtesting).
- `collectors/warrants/docs/WARRANTS_COMPONENT.md` — capital-structure data sourcing
  (DilutionWatch pivot), `core.security` design.
- `docs/Master_Data_Requirements_Web_Sources_v2.csv` — the original field-by-field
  data requirements this and the capital-structure pivot were derived from.
