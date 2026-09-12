# Backtesting Component — Architecture Decision and Delivery Plan

**Project:** QuantLab
**Domain:** Historical Intraday Predictive Replay
**Component:** Backtesting
**Status:** Approved for implementation (vertical slice first)

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
- **Intraday data provider:** deferred behind an adapter interface. Databento
  (`XNAS.ITCH`) and Massive (consolidated SIP) remain the two candidates; the choice
  is made once the indicators actually needed are better known. Nothing downstream
  (Feature Engine, models, viewer) depends on which provider is picked.

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
DatabentoAdapter ──┐
MassiveAdapter ────┼──► QuantLab Canonical Model (raw/core.market_bar_1m)
StubAdapter/CSV ───┘
```

A change of intraday provider must never require changing the Feature Engine or any
model.

### 6. Scientific reproducibility

Every backtest run records dataset version, feature version, model id/version,
parameters, ticker universe, period and Git commit, so any result can be traced back
to the exact code and data that produced it.

## Initial logical data model (candidate — finalized per chantier)

### `raw.market_bar_1m` / `core.market_bar_1m`

One row per ticker/minute. Only 1-minute OHLCV is persisted; every larger timeframe
(2m/5m/15m/30m/1h/daily) is computed on demand by the Aggregation Engine, never
depended upon from a provider's own aggregation.

Candidate fields: `ticker`, `market`, `bar_start` (UTC, explicit trading-session
timezone semantics — see BT-00), `open`, `high`, `low`, `close`, `volume`, `source`,
`retrieved_at`.

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
from whatever is next-free at implementation time, not reserved in advance — e.g.
`017` is currently held by the in-progress `sec-15-llm-warrant-term-extraction`
branch.

## Validation plan (vertical slice, not full backfill)

Before any real provider integration:

1. Pick one reference ticker/day already known in the repo (GPUS, 2026-08-14 — an
   existing validated Nasdaq HALT reference case) and build a small fixture CSV.
2. Prove the Aggregation Engine is 100% deterministic against that fixture.
3. Prove `MarketContext(as_of=...)` technically rejects any read past the simulated
   clock (the single most important test in this component).
4. Prove one or two simple features (VWAP, RVOL) match a golden dataset.
5. Only then wire the viewer and, later, a real provider and a real model.

Full historical backfill and provider selection are deliberately deferred past this
point (see `BACKTESTING_GITHUB_BACKLOG.md`, Slice 3).

## Long-term target

```text
Databento / Massive / (stub for dev)
        |
        v
collectors/market_data (adapters -> canonical model)
        |
        v
raw.market_bar_1m
        |
        v
core.market_bar_1m
        |
        v
Replay Engine (Simulated Clock + MarketContext)
        |
        v
Aggregation Engine (1m -> 2m -> 5m -> ... -> daily)
        |
        v
Feature Engine (market / halts / warrants / convertibles / fundamentals / sec)
        |
        v
Model Engine -> Prediction Log -> Prediction Evaluation
        |
        v
Interactive Viewer (ui/replay) <-> Batch Replay (orchestration/jobs)
```

Halts features reuse `analytics/nasdaq_halts` as-is. Warrants/convertibles features
depend on `core.security` / `core.warrant` from the warrants component (see
`collectors/warrants/docs/WARRANTS_COMPONENT.md`) — this dependency must be
coordinated explicitly (BT-14) rather than duplicated.

QuantConnect LEAN and VectorBT remain optional, future, complementary tools for the
later Trading Simulation phase — QuantLab is not built around either.
