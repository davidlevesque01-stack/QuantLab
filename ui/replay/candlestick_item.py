"""Candlestick chart item for the replay viewer (BT-06a).

pyqtgraph has no built-in candlestick item -- this follows pyqtgraph's own
documented recipe (a QPicture-backed GraphicsObject) rather than inventing
a different approach.
"""

from __future__ import annotations

import pyqtgraph as pg
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPicture


class CandlestickItem(pg.GraphicsObject):
    """Renders OHLC candles from (x, open, high, low, close) tuples, where
    x is numeric (minutes elapsed since the replay session start).
    """

    UP_COLOR = "g"
    DOWN_COLOR = "r"

    def __init__(self, candles: list[tuple[float, float, float, float, float]]):
        super().__init__()
        self._picture = QPicture()
        self._generate_picture(candles)

    def _generate_picture(self, candles: list[tuple[float, float, float, float, float]]) -> None:
        self._picture = QPicture()
        painter = QPainter(self._picture)

        half_width = 0.35

        for x, open_, high, low, close in candles:
            painter.setPen(pg.mkPen("w"))
            painter.drawLine(pg.QtCore.QPointF(x, low), pg.QtCore.QPointF(x, high))

            color = self.UP_COLOR if close >= open_ else self.DOWN_COLOR
            painter.setPen(pg.mkPen(color))
            painter.setBrush(pg.mkBrush(color))

            body_top = max(open_, close)
            body_bottom = min(open_, close)
            painter.drawRect(
                QRectF(x - half_width, body_bottom, half_width * 2, body_top - body_bottom)
            )

        painter.end()

    def paint(self, painter, *args) -> None:
        painter.drawPicture(0, 0, self._picture)

    def boundingRect(self) -> QRectF:
        return QRectF(self._picture.boundingRect())
