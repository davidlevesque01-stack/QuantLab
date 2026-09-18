from datetime import date, datetime

import pytest
from PySide6.QtWidgets import QApplication

from ui.replay.main_window import MainWindow

TICKER = "GPUS"
TRADING_DAY = date(2026, 8, 14)


class FakeMarketBarSource:
    def fetch_bars(self, *, ticker, trading_day, as_of):
        return []


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_instantiates_replay_engine_for_requested_ticker_and_day(qapp):
    window = MainWindow(
        ticker=TICKER,
        trading_day=TRADING_DAY,
        market_bar_source=FakeMarketBarSource(),
    )

    assert window.replay_engine.ticker == TICKER
    assert window.replay_engine.trading_day == TRADING_DAY


def test_main_window_starts_at_pre_market_open(qapp):
    window = MainWindow(
        ticker=TICKER,
        trading_day=TRADING_DAY,
        market_bar_source=FakeMarketBarSource(),
    )

    assert window.replay_engine.current_time == datetime(2026, 8, 14, 4, 0, 0)


def test_main_window_rejects_non_trading_day(qapp):
    with pytest.raises(ValueError):
        MainWindow(
            ticker=TICKER,
            trading_day=date(2026, 8, 15),  # a Saturday
            market_bar_source=FakeMarketBarSource(),
        )
