# Backtesting Component — Initial GitHub Backlog

Recommended initial issues for the QuantLab GitHub Project. Sequenced as a vertical
slice first (Slice 1), then prediction/batch (Slice 2), then real data and rigorous
validation (Slice 3). Status is tracked on the GitHub Project board, not in this file.

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

## BT-05 — Replay Engine, interactive mode (no viewer, no model yet)

**Goal:** Orchestrate clock -> context -> aggregation -> features end-to-end on the fixture.

**Acceptance criteria**
- Single `ReplayEngine` class in `analytics/replay/` drives the full loop for one
  ticker/day and exposes state at each simulated minute (no PySide6 dependency).
- Designed so Interactive Replay and Batch Replay (BT-09) reuse it unchanged.

## BT-06 — Minimal viewer (`ui/replay/`)

**Goal:** Visually replay the GPUS fixture minute by minute.

**Acceptance criteria**
- `ui/replay/` built with `pyqtgraph`, following the `AnalysisService` instantiation
  pattern from `ui/nasdaq_halts/main_window.py`.
- Candlestick + volume + feature panel, with PLAY/PAUSE/+1min/-1min/timeline
  controls driving the `SimulatedClock`.
- Manually verified by actually running the app and replaying GPUS 2026-08-14 —
  automated tests alone do not certify this ticket.

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

## BT-11 — Real intraday data provider integration

**Goal:** Replace the stub/CSV adapter with a real Databento or Massive adapter.

**Acceptance criteria**
- Provider decision made and documented (which indicators drove the choice).
- New adapter implements the same `QuantLabAdapter` interface from BT-01 — zero
  changes required in the Feature Engine or models.
- API credentials handled via environment variables only, never committed.

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
- Warrants/convertibles features are coordinated explicitly with the warrants
  component (`core.security` / `core.warrant` from
  `collectors/warrants/docs/WARRANTS_COMPONENT.md`) to avoid a duplicated data model.
