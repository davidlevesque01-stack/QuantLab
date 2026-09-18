import pytest
from PySide6.QtWidgets import QApplication

from ui.replay.candlestick_item import HALF_WIDTH, CandlestickItem


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_bounding_rect_matches_real_data_precisely_for_sub_dollar_prices(qapp):
    # Regression test for issue #118: QPicture.boundingRect() rounds to
    # integer coordinates, collapsing a sub-$1 ticker's real price range
    # (e.g. 0.39-0.42) to a degenerate ~1-unit box. boundingRect() must be
    # computed from the actual candle data at full float precision.
    candles = [
        (0.0, 0.40, 0.42, 0.39, 0.41),
        (1.0, 0.41, 0.45, 0.40, 0.44),
        (2.0, 0.44, 0.44, 0.38, 0.39),
    ]

    item = CandlestickItem(candles)
    rect = item.boundingRect()

    assert rect.left() == pytest.approx(0.0 - HALF_WIDTH)
    assert rect.right() == pytest.approx(2.0 + HALF_WIDTH)
    assert rect.top() == pytest.approx(0.38)  # min low
    assert rect.bottom() == pytest.approx(0.45)  # max high


def test_bounding_rect_empty_for_no_candles(qapp):
    item = CandlestickItem([])

    assert item.boundingRect().isEmpty()


def test_paint_does_not_use_qpicture(qapp):
    # Regression guard for issue #118's root cause: drawing through
    # QPicture's record/playback lost float precision for certain
    # coordinates and produced phantom full-height spikes for a real
    # sub-$1 ticker (GIPR). CandlestickItem must draw directly in paint(),
    # not via a cached QPicture.
    import inspect

    source = inspect.getsource(CandlestickItem.paint)
    assert "QPicture" not in source
    assert "drawPicture" not in source
