from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from analytics.replay.market_context import LookAheadViolation, MarketContext

AS_OF = datetime(2026, 8, 14, 10, 17, 0)
TICKER = "GPUS"
TRADING_DAY = date(2026, 8, 14)


class FakeMarketBarSource:
    """Stands in for MarketBarSource -- returns whatever bars() the test
    configures, regardless of the as_of it's called with, so tests can
    prove MarketContext rejects a violating row even when the underlying
    source misbehaves (doesn't actually honor the filter).
    """

    def __init__(self, bars):
        self._bars = bars
        self.calls = []

    def fetch_bars(self, *, ticker, trading_day, as_of):
        self.calls.append({"ticker": ticker, "trading_day": trading_day, "as_of": as_of})
        return self._bars


def _bar(bar_start):
    return {
        "ticker": TICKER,
        "market": "Q",
        "bar_start": bar_start,
        "open": 1.0,
        "high": 1.0,
        "low": 1.0,
        "close": 1.0,
        "volume": 100,
    }


def test_assert_visible_allows_timestamp_at_as_of():
    context = MarketContext(as_of=AS_OF)

    context.assert_visible(AS_OF)  # does not raise


def test_assert_visible_allows_timestamp_before_as_of():
    context = MarketContext(as_of=AS_OF)

    context.assert_visible(datetime(2026, 8, 14, 10, 16, 0))  # does not raise


def test_assert_visible_rejects_timestamp_after_as_of():
    context = MarketContext(as_of=AS_OF)

    with pytest.raises(LookAheadViolation):
        context.assert_visible(datetime(2026, 8, 14, 10, 18, 0))


def test_assert_visible_rejects_aware_timestamp():
    context = MarketContext(as_of=AS_OF)
    aware = datetime(2026, 8, 14, 10, 0, 0, tzinfo=ZoneInfo("UTC"))

    with pytest.raises(ValueError):
        context.assert_visible(aware)


def test_construction_rejects_aware_as_of():
    aware = datetime(2026, 8, 14, 10, 17, 0, tzinfo=ZoneInfo("UTC"))

    with pytest.raises(ValueError):
        MarketContext(as_of=aware)


def test_fetch_bars_raises_without_configured_source():
    context = MarketContext(as_of=AS_OF)

    with pytest.raises(RuntimeError):
        context.fetch_bars(ticker=TICKER, trading_day=TRADING_DAY)


def test_fetch_bars_delegates_with_as_of_bound():
    source = FakeMarketBarSource(bars=[_bar(datetime(2026, 8, 14, 9, 30, 0))])
    context = MarketContext(as_of=AS_OF, market_bar_source=source)

    bars = context.fetch_bars(ticker=TICKER, trading_day=TRADING_DAY)

    assert len(bars) == 1
    assert source.calls == [{"ticker": TICKER, "trading_day": TRADING_DAY, "as_of": AS_OF}]


def test_fetch_bars_structurally_rejects_a_violating_row_from_the_source():
    # The single most important test in this component
    # (docs/backtesting/BACKTESTING_COMPONENT.md validation plan item 3):
    # even if the underlying source ignores as_of and returns a bar past
    # it, MarketContext must reject it, not silently pass it through.
    violating_bar = _bar(datetime(2026, 8, 14, 10, 18, 0))  # 1 minute after AS_OF
    source = FakeMarketBarSource(bars=[violating_bar])
    context = MarketContext(as_of=AS_OF, market_bar_source=source)

    with pytest.raises(LookAheadViolation):
        context.fetch_bars(ticker=TICKER, trading_day=TRADING_DAY)


def test_fetch_bars_allows_a_bar_exactly_at_as_of():
    source = FakeMarketBarSource(bars=[_bar(AS_OF)])
    context = MarketContext(as_of=AS_OF, market_bar_source=source)

    bars = context.fetch_bars(ticker=TICKER, trading_day=TRADING_DAY)

    assert len(bars) == 1
