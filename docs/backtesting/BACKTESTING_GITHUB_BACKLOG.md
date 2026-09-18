# Backtesting Component — Initial GitHub Backlog

Recommended initial issues for the QuantLab GitHub Project. Sequenced as a vertical
slice first (Slice 1), then prediction/batch (Slice 2), then real data and rigorous
validation (Slice 3). Status is tracked on the GitHub Project board, not in this file.

**Revision note (BT-15):** the intraday provider decision is no longer open —
Massive (formerly Polygon.io) US Stocks SIP `minute_aggs_v1` is confirmed (see
`BACKTESTING_COMPONENT.md`, "Provider decision (v2)"). This moves real-provider
integration (BT-11) earlier than originally sequenced, and requires an additive
schema migration (BT-16) plus a Source Adapter / Historical Data API layering
correction (BT-17) before BT-11 can land cleanly. BT-01 through BT-10 are otherwise
unaffected — the fixture/CSV path stays the primary path for automated tests.

**Revision note (MVP skeleton, 2026-09-18):** there is no market data in
PostgreSQL yet outside the BT-01 fixture, and the user will have a Massive
account/API key the same day this note was written. Priority shifts to the
shortest real path from ingestion to an on-screen chart, deferring aggregation,
features, models and capital-structure integration until that skeleton renders:

```text
BT-16 (schema) -> BT-11 (real MassiveAdapter) -> BT-17 (Historical Data API)
    -> BT-03 (Simulated Clock/MarketContext) -> BT-05 (Replay Engine, trimmed)
    -> BT-06a (bare candlestick+volume viewer)
```

`BT-16`'s `security_id` becomes **nullable** for this pass specifically so it
does not block on `core.security`/CS-07 (capital-structure schema) — that
coordination still happens, just not on this skeleton's critical path. `BT-06`
is split into `BT-06a` (bare chart, no feature panel — part of the skeleton) and
`BT-06b` (feature panel, after BT-04). `BT-05` is trimmed for this pass to
clock -> context -> raw bars only, deferring the aggregation/feature steps in its
own loop to a follow-up once the skeleton renders. BT-02/BT-04/BT-06b/CS-07 and
everything capital-structure move after the skeleton, not before it.

## BT-00 — Backtesting foundations

**Goal:** Put the cross-cutting prerequisites in place before any replay code is written.

**Acceptance criteria**
- `pandas`/`numpy` added to `pyproject.toml` and pinned in `requirements.txt`.
- `shared/calendar/trading_calendar.py` extended with pre-market (04:00) / regular
  (09:30-16:00) / after-hours (20:00) sessions.
- Nasdaq market-data timestamp timezone semantics formalized (closes the debt noted
  in `docs/architecture.md` §22 instead of inheriting it unresolved).
- `docs/backtesting/` scaffolding in place (this file and `BACKTESTING_COMPONENT.md`).

## BT-01 — Canonical market bar model + stub/CSV market data collector

**Goal:** Persist 1-minute OHLCV for one fixture ticker/day without depending on a real provider.

**Acceptance criteria**
- `collectors/market_data/` created following the `collectors/nasdaq_halts` pattern
  (`src/`, `data/{raw,processed}/`, `logs/`, `config/config.json` with env-override
  path resolution).
- `QuantLabAdapter` interface defined; a `StubAdapter`/CSV adapter implements it
  against a small local fixture (e.g. GPUS, 2026-08-14).
- A new migration creates `raw.market_bar_1m` / `core.market_bar_1m`, numbered from
  whatever is the next free migration at implementation time (`017` is already taken
  by `017_add_extraction_method_to_sec_8k_warrant_text_extraction.sql`, merged via
  SEC-15 — do not assume any specific number is free); a new advisory lock objid is
  registered in
  `docs/database.md` §21 (verify the actual next-free objid at implementation time —
  do not assume 10 is still free).
- Persistence is idempotent (rerun produces 0 inserted / N unchanged), uses
  `shared/database/connection.get_connection()` only.
- Tests pass.

**Retroactive note (BT-15):** `QuantLabAdapter.fetch_bars()` turned out to conflate
ingestion (Source Adapter) with replay-time reads (Historical Data API) — see BT-17.
`csv_adapter.py` itself stays correct as an ingestion-side stub; nothing here needs
to be reverted, only extended.

## BT-02 — Aggregation Engine (1m -> 2m -> 5m -> ... -> daily)

**Goal:** Deterministic bar aggregation with explicit closed/in-progress bar handling.

**Acceptance criteria**
- `OPEN`/`HIGH`/`LOW`/`CLOSE`/`VOLUME` aggregation rules implemented and 100%
  deterministic (no unexplained floating-point tolerance).
- Closed Bar vs. In-Progress Bar explicitly modeled and tested (an in-progress 5m
  bar at 10:17 must never expose its final high/low/close/volume).
- pytest suite covers 1m->2m, 1m->5m, 1m->15m, 1m->30m, 1m->1h, 1m->daily.

## BT-03 — Simulated Clock + MarketContext (point-in-time guard)

**Goal:** Make look-ahead bias structurally impossible, not just discouraged by convention.

**Acceptance criteria**
- `SimulatedClock` and `MarketContext(as_of=...)` implemented in `analytics/replay/`.
- A request for `information_timestamp > as_of` is technically rejected (raises,
  not silently filtered) — covered by dedicated pytest cases.
- This ticket blocks BT-04 and everything downstream: no feature/model code is
  built on top of an unguarded context.

## BT-04 — Minimal Feature Engine (VWAP, RVOL) with golden dataset

**Goal:** Prove `analytics/replay/features/market/` produces correct point-in-time indicators.

**Acceptance criteria**
- `calculate(ticker, as_of, timeframe)` signature implemented for VWAP and RVOL.
- Golden dataset added under `tests/golden/` with expected values at known
  timestamps for the GPUS fixture.
- Values recomputed at each simulated minute match the golden dataset exactly.

## BT-05 — Replay Engine, interactive mode (trimmed for the MVP skeleton)

**Goal:** Orchestrate clock -> context -> raw bars end-to-end on real Massive
data. Aggregation and features are deliberately deferred to a follow-up pass
once BT-06a renders — this ticket's scope is trimmed, not its design: the loop
must still be shaped so BT-02/BT-04 slot in later without rework.

**Acceptance criteria**
- Single `ReplayEngine` class in `analytics/replay/` drives the full loop for one
  ticker/day and exposes state at each simulated minute (no PySide6 dependency).
- Designed so Interactive Replay and Batch Replay (BT-09) reuse it unchanged.
- Reads market bars through the Historical Data API (BT-17's `MarketBarSource`),
  never through a Source Adapter directly.
- No aggregation/feature step in this pass — raw 1-minute bars only, exposed in
  a shape BT-02/BT-04 can slot into later without changing `ReplayEngine`'s
  public interface.

## BT-06a — Minimal viewer skeleton: candlestick + volume, no features

**Goal:** Prove the full pipe (Massive -> RAW -> CORE -> Replay -> screen)
renders real data, before any indicator/model work. This is the MVP skeleton's
finish line.

**Acceptance criteria**
- `ui/replay/` built with `pyqtgraph`, following the `AnalysisService`
  instantiation pattern from `ui/nasdaq_halts/main_window.py`.
- Candlestick + volume only — no feature panel (that's BT-06b), no timeframe
  picker (that needs BT-02, not in this pass).
- PLAY/PAUSE/+1min/-1min/timeline controls driving the `SimulatedClock`.
- Manually verified against a real ticker/day ingested via BT-11 (Massive),
  not the BT-01 fixture — automated tests alone do not certify this ticket.

## BT-06b — Viewer feature panel (VWAP/RVOL)

**Goal:** Add BT-04's indicators to the BT-06a skeleton once it renders.

**Acceptance criteria**
- Feature panel added to `ui/replay/` showing VWAP/RVOL from BT-04.
- Timeframe picker ([1M][2M][5M]...) added once BT-02's Aggregation Engine
  is available.
- Manually verified the same way as BT-06a.

## BT-07 — Model Engine + prediction persistence

**Goal:** Plug a trivial baseline model into the replay loop and persist predictions.

**Acceptance criteria**
- Pluggable model interface in `analytics/replay/` (baseline heuristic model for
  MVP wiring — real ML is a later phase).
- `core.backtest_run` / `core.backtest_prediction` created by migration, with
  reproducibility fields (dataset version, feature version, model id/version,
  parameters, ticker universe, period, Git commit, execution timestamp).

## BT-08 — Prediction Evaluation

**Goal:** Score each prediction against what actually happened after its horizon.

**Acceptance criteria**
- `core.backtest_prediction_evaluation` populated with max return, max price, time
  to target, min return, and a SUCCESS/FAILURE result per prediction.
- Evaluation only runs once the replay has advanced past the prediction horizon
  (no partial/early scoring).

## BT-09 — Batch Replay

**Goal:** Reuse the same Replay Engine to run thousands of ticker/day scenarios.

**Acceptance criteria**
- CLI entry point under `orchestration/jobs/`, runnable as
  `python -m orchestration.jobs...` like existing collectors.
- Confirmed to reuse `ReplayEngine` from BT-05 unchanged (no parallel batch-only
  implementation of the replay loop).

## BT-10 — Prediction markers + MODEL panel in the viewer

**Goal:** Surface predictions and their evaluation in the interactive viewer.

**Acceptance criteria**
- Prediction/probability/target displayed live as the replay advances.
- HALT and prediction markers rendered on the timeline.

## BT-11 — Real intraday data provider integration (Massive)

**Goal:** Replace the stub/CSV adapter with a real `MassiveAdapter` — resequenced
earlier (was end of Slice 3; now depends only on BT-16/BT-17, not on BT-08..BT-10).

**Acceptance criteria**
- Provider decision already made (Massive, `minute_aggs_v1` — see
  `BACKTESTING_COMPONENT.md`, "Provider decision (v2)"); this ticket is
  implementation, not decision-making.
- `MassiveAdapter` downloads and parses one day's whole-market flat file and calls
  `persist_market_bars()` for every relevant row — it does not answer live
  per-ticker requests (that's the Historical Data API's job, BT-17).
- Implements the same `QuantLabAdapter` interface from BT-01 — zero changes
  required in the Feature Engine or models.
- API credentials (`QUANTLAB_MASSIVE_API_KEY` or similar) handled via environment
  variables only, never committed.
- Raw flat files retained with a checksum (SHA-256) alongside provenance metadata.

## BT-15 — Revise backtesting docs for Massive/Polygon provider decision

**Goal:** Bring `BACKTESTING_COMPONENT.md`/`BACKTESTING_GITHUB_BACKLOG.md` in line
with the confirmed provider decision and the Source Adapter / Historical Data API
layering correction — documentation only, no code/schema change in this ticket.

**Acceptance criteria**
- Provider decision, richer canonical schema plan, and validation strategy
  documented in `BACKTESTING_COMPONENT.md`.
- `.drawio`/`.svg` functional architecture diagrams committed alongside the ASCII
  diagrams (kept in sync by hand).
- `docs/data_sources.md` created as a cross-cutting provider registry.
- BT-01/BT-05/BT-11 backlog entries updated to reflect the layering correction and
  resequencing (this file).

## BT-16 — Additive migration for the richer `market_bar_1m` schema

**Goal:** Add `security_id`/`market_scope`/`session`/`transaction_count`/
`source_provider`/`source_dataset`/`dataset_version`/`ingestion_run_id` without
touching the already-applied migration 018.

**Acceptance criteria**
- New migration numbered from whatever is next-free at implementation time; `018`
  is never edited retroactively.
- `market` (venue letter code) becomes nullable/optional rather than removed.
- `security_id` is added as a **nullable** FK into `core.security` — deliberately
  not blocking on CS-07 for the MVP skeleton pass. It stays unpopulated until
  `core.security` exists and a backfill is done; `ticker` (already present)
  remains the working identifier until then. Coordinate the eventual FK
  shape with the capital-structure component
  (`collectors/warrants/docs/WARRANTS_COMPONENT.md`) rather than inventing it
  twice, but do not let that coordination block this ticket.
- `session` computed at ingestion from `shared/calendar/trading_calendar.get_session_bounds()`.

## BT-17 — Historical Data API (`MarketBarSource`), separated from the Source Adapter

**Goal:** Give the Replay Engine a read-only path to `core.market_bar_1m` that
never calls a Source Adapter directly.

**Acceptance criteria**
- `analytics/replay/market_bar_source.py` added, mirroring the read-only pattern of
  `analytics/nasdaq_halts/core_source.py`.
- `ReplayEngine` (BT-05) consumes this, not `QuantLabAdapter.fetch_bars()` directly.
- `CSVAdapter`/`MassiveAdapter` (BT-01/BT-11) remain Source Adapters — ingestion
  only, never read by the Replay Engine at replay time.

## BT-12 — Source/RAW validation

**Goal:** Automated data-quality guards plus an independent reference comparison.

**Acceptance criteria**
- Automated checks: timestamps, duplicates, missing bars, timezone, session, OHLC
  consistency (`HIGH >= OPEN/CLOSE`, `LOW <= OPEN/CLOSE`, `VOLUME >= 0`),
  chronological ordering.
- Minute-by-minute comparison against an independent reference (e.g. TradingView)
  for a reference set of tickers/days, with an automated discrepancy report.

## BT-13 — Replay Equivalence Test

**Goal:** Prove replayed minute-by-minute computation matches full-history computation.

**Acceptance criteria**
- For applicable metrics, `full historical calculation == replay calculation @ end
  of day`, automated and run as part of the test suite.
- Any discrepancy is treated as a state/aggregation/timestamp/feature bug, not
  tolerated as noise.

## BT-14 — Feature Engine extension (halts / warrants / convertibles / fundamentals / sec)

**Goal:** Extend point-in-time features beyond raw market data.

**Acceptance criteria**
- Halts features reuse `analytics/nasdaq_halts` as-is (no duplicated halt logic).
- Warrants/convertibles/security features are coordinated explicitly with the
  capital-structure component (`core.security` / `core.security_snapshot` from
  `collectors/warrants/docs/WARRANTS_COMPONENT.md`, updated for the DilutionWatch
  pivot) to avoid a duplicated data model.
- ITM/resistance-style derived metrics (warrant/convertible terms vs. live price)
  are computed here, in the Feature Engine, from raw terms + `core.market_bar_1m` —
  never sourced pre-computed from an external vendor.
