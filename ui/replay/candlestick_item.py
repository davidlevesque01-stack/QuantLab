"""Candlestick chart item for the replay viewer (BT-06a).

Draws directly in paint() rather than caching a QPicture -- pyqtgraph's own
documented candlestick recipe uses a QPicture-backed GraphicsObject, but
QPicture's internal recording/playback format loses precision for certain
float coordinates in a way that corrupted rendering: manual verification
against real Massive data (GIPR, 2026-09-17, a sub-$1 ticker) showed
recurring phantom full-height vertical spikes with no corresponding data
(confirmed via direct SQL: no bar on that day has a high-low range above
$0.15, ruling out real price action). Switching from
`painter.drawPicture(...)` playback to drawing each candle directly in
paint() eliminated the artifacts entirely, reproduced and verified against
the exact real dataset. See issue #118.

boundingRect() is computed directly from the candle data (min/max of
low/high, full float precision) rather than from any Qt-native bounding
rect helper -- pyqtgraph's ViewBox uses this for Y-axis auto-ranging
(GraphicsObject has no dataBounds() override), so it must be precise.
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import QRectF

HALF_WIDTH = 0.35


class CandlestickItem(pg.GraphicsObject):
    """Renders OHLC candles from (x, open, high, low, close) tuples, where
    x is numeric (minutes elapsed since the replay session start).
    """

    UP_COLOR = "g"
    DOWN_COLOR = "r"

    def __init__(self, candles: list[tuple[float, float, float, float, float]]):
        super().__init__()
        self._candles = candles
        self._bounding_rect = self._compute_bounding_rect(candles)

    @staticmethod
    def _compute_bounding_rect(candles: list[tuple[float, float, float, float, float]]) -> QRectF:
        if not candles:
            return QRectF()

        xs = [c[0] for c in candles]
        lows = [c[3] for c in candles]
        highs = [c[2] for c in candles]

        min_x = min(xs) - HALF_WIDTH
        max_x = max(xs) + HALF_WIDTH
        min_y = min(lows)
        max_y = max(highs)

        return QRectF(min_x, min_y, max_x - min_x, max_y - min_y)

    def paint(self, painter, *args) -> None:
        for x, open_, high, low, close in self._candles:
            painter.setPen(pg.mkPen("w"))
            painter.drawLine(pg.QtCore.QPointF(x, low), pg.QtCore.QPointF(x, high))

            color = self.UP_COLOR if close >= open_ else self.DOWN_COLOR
            painter.setPen(pg.mkPen(color))
            painter.setBrush(pg.mkBrush(color))

            body_top = max(open_, close)
            body_bottom = min(open_, close)
            painter.drawRect(
                QRectF(x - HALF_WIDTH, body_bottom, HALF_WIDTH * 2, body_top - body_bottom)
            )

    def boundingRect(self) -> QRectF:
        return self._bounding_rect
