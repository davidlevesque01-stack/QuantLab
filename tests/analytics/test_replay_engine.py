from datetime import date, datetime

import pytest

from analytics.replay.market_context import LookAheadViolation
from analytics.replay.replay_engine import ReplayEngine

TICKER = "GPUS"
TRADING_DAY = date(2026, 8, 14)  # a Friday, trading day


class FakeMarketBarSource:
    """Mimics MarketBarSource's own as_of filtering, so tests exercise
    ReplayEngine's stepping logic without needing a real DB.
    """

    def __init__(self, bars):
        self._bars = bars
        self.calls = []

    def fetch_bars(self, *, ticker, trading_day, as_of):
        self.calls.append({"ticker": ticker, "trading_day": trading_day, "as_of": as_of})
        return [b for b in self._bars if b["bar_start"] <= as_of]


class MisbehavingMarketBarSource:
    """Ignores as_of entirely -- returns every configured bar regardless.
    Used only to prove MarketContext's defense-in-depth still rejects a
    violation even when the underlying source doesn't filter correctly.
    """

    def __init__(self, bars):
        self._bars = bars

    def fetch_bars(self, *, ticker, trading_day, as_of):
        return self._bars


def _bar(bar_start, ticker=TICKER):
    return {
        "ticker": ticker,
        "market": "Q",
        "bar_start": bar_start,
        "open": 1.0,
        "high": 1.0,
        "low": 1.0,
        "close": 1.0,
        "volume": 100,
    }


def test_construction_rejects_non_trading_day():
    saturday = date(2026, 8, 15)

    with pytest.raises(ValueError):
        ReplayEngine(ticker=TICKER, trading_day=saturday)


def test_default_start_and_end_time_span_the_extended_session():
    source = FakeMarketBarSource(bars=[])
    engine = ReplayEngine(ticker=TICKER, trading_day=TRADING_DAY, market_bar_source=source)

    assert engine.current_time == datetime(2026, 8, 14, 4, 0, 0)


def test_state_reflects_only_bars_visible_at_current_time():
    bars = [
        _bar(datetime(2026, 8, 14, 9, 30, 0)),
        _bar(datetime(2026, 8, 14, 9, 31, 0)),
        _bar(datetime(2026, 8, 14, 9, 32, 0)),
    ]
    source = FakeMarketBarSource(bars=bars)
    engine = ReplayEngine(
        ticker=TICKER,
        trading_day=TRADING_DAY,
        market_bar_source=source,
        start_time=datetime(2026, 8, 14, 9, 30, 0),
    )

    state = engine.state

    assert state.current_time == datetime(2026, 8, 14, 9, 30, 0)
    assert state.ticker == TICKER
    assert state.trading_day == TRADING_DAY
    assert [b["bar_start"] for b in state.bars] == [datetime(2026, 8, 14, 9, 30, 0)]


def test_advance_grows_visible_bars():
    bars = [
        _bar(datetime(2026, 8, 14, 9, 30, 0)),
        _bar(datetime(2026, 8, 14, 9, 31, 0)),
    ]
    source = FakeMarketBarSource(bars=bars)
    engine = ReplayEngine(
        ticker=TICKER,
        trading_day=TRADING_DAY,
        market_bar_source=source,
        start_time=datetime(2026, 8, 14, 9, 30, 0),
    )

    assert len(engine.state.bars) == 1

    state = engine.advance()

    assert state.current_time == datetime(2026, 8, 14, 9, 31, 0)
    assert len(state.bars) == 2


def test_rewind_shrinks_visible_bars():
    # Central test: proves each step rebuilds a fresh MarketContext rather
    # than leaking/accumulating state -- rewinding must un-reveal bars.
    bars = [
        _bar(datetime(2026, 8, 14, 9, 30, 0)),
        _bar(datetime(2026, 8, 14, 9, 31, 0)),
    ]
    source = FakeMarketBarSource(bars=bars)
    engine = ReplayEngine(
        ticker=TICKER,
        trading_day=TRADING_DAY,
        market_bar_source=source,
        start_time=datetime(2026, 8, 14, 9, 31, 0),
    )

    assert len(engine.state.bars) == 2

    state = engine.rewind()

    assert state.current_time == datetime(2026, 8, 14, 9, 30, 0)
    assert len(state.bars) == 1


def test_seek_jumps_to_arbitrary_time():
    bars = [_bar(datetime(2026, 8, 14, 15, 0, 0))]
    source = FakeMarketBarSource(bars=bars)
    engine = ReplayEngine(ticker=TICKER, trading_day=TRADING_DAY, market_bar_source=source)

    state = engine.seek(datetime(2026, 8, 14, 15, 30, 0))

    assert state.current_time == datetime(2026, 8, 14, 15, 30, 0)
    assert len(state.bars) == 1


def test_run_yields_one_state_per_minute_from_start_to_end_inclusive():
    source = FakeMarketBarSource(bars=[])
    engine = ReplayEngine(
        ticker=TICKER,
        trading_day=TRADING_DAY,
        market_bar_source=source,
        start_time=datetime(2026, 8, 14, 9, 30, 0),
        end_time=datetime(2026, 8, 14, 9, 33, 0),
    )

    states = list(engine.run())

    assert [s.current_time for s in states] == [
        datetime(2026, 8, 14, 9, 30, 0),
        datetime(2026, 8, 14, 9, 31, 0),
        datetime(2026, 8, 14, 9, 32, 0),
        datetime(2026, 8, 14, 9, 33, 0),
    ]


def test_look_ahead_violation_propagates_through_replay_engine():
    # The point-in-time guard (BT-03) must not be bypassable through
    # ReplayEngine: a misbehaving source that ignores as_of still gets
    # rejected structurally.
    start_time = datetime(2026, 8, 14, 9, 30, 0)
    violating_bar = _bar(datetime(2026, 8, 14, 9, 31, 0))  # 1 minute after start
    source = MisbehavingMarketBarSource(bars=[violating_bar])
    engine = ReplayEngine(
        ticker=TICKER,
        trading_day=TRADING_DAY,
        market_bar_source=source,
        start_time=start_time,
    )

    with pytest.raises(LookAheadViolation):
        engine.state
