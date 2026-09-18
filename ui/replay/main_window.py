"""Minimal replay viewer skeleton (BT-06a): candlestick + volume, no
features, no timeframe picker (those are BT-06b/BT-02's job). Proves the
full pipe (Massive -> RAW -> CORE -> Replay -> screen) renders real data.

Instantiates ReplayEngine directly in __init__, mirroring the
AnalysisService(core_source=...) instantiation pattern from
ui/nasdaq_halts/main_window.py (see docs/backtesting/
BACKTESTING_GITHUB_BACKLOG.md#bt-06a).

PLAY/PAUSE/+1min/-1min/timeline controls drive ReplayEngine.advance()/
.rewind()/.seek() directly -- ReplayEngine (BT-05) does not compose
SimulatedClock internally (see its own module docstring: "PLAY/PAUSE
timing is BT-06a's job"), so there is no separate SimulatedClock instance
to wire up here; ReplayEngine already exposes the same stepping shape.
"""

from __future__ import annotations

from datetime import date, datetime

import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from shared.calendar.trading_calendar import get_session_bounds

from analytics.replay.market_bar_source import MarketBarSource
from analytics.replay.replay_engine import ReplayEngine
from ui.replay.candlestick_item import CandlestickItem

PLAY_INTERVAL_MS = 300


class MainWindow(QMainWindow):
    def __init__(self, ticker: str, trading_day: date, market_bar_source=None) -> None:
        super().__init__()

        bounds = get_session_bounds(trading_day)
        if bounds is None:
            raise ValueError(f"{trading_day} is not a Nasdaq trading day")

        self._start_time = datetime.combine(trading_day, bounds.pre_market_open)
        self._end_time = datetime.combine(trading_day, bounds.after_hours_close)
        self._total_minutes = int((self._end_time - self._start_time).total_seconds() // 60)

        self.replay_engine = ReplayEngine(
            ticker=ticker,
            trading_day=trading_day,
            market_bar_source=market_bar_source or MarketBarSource(),
            start_time=self._start_time,
            end_time=self._end_time,
        )

        self.setWindowTitle(f"QuantLab - Replay Viewer - {ticker} {trading_day.isoformat()}")
        self.resize(1000, 700)

        self._play_timer = QTimer(self)
        self._play_timer.setInterval(PLAY_INTERVAL_MS)
        self._play_timer.timeout.connect(self._on_play_tick)

        central = QWidget()
        layout = QVBoxLayout(central)

        self._time_label = QLabel()
        layout.addWidget(self._time_label)

        self._chart = pg.GraphicsLayoutWidget()
        self._price_plot = self._chart.addPlot(row=0, col=0)
        self._price_plot.setLabel("left", "Price")
        self._price_plot.setXRange(0, self._total_minutes)
        self._chart.nextRow()
        self._volume_plot = self._chart.addPlot(row=1, col=0)
        self._volume_plot.setLabel("left", "Volume")
        self._volume_plot.setLabel("bottom", "Minutes since session start (04:00 ET)")
        self._volume_plot.setXLink(self._price_plot)
        self._chart.ci.layout.setRowStretchFactor(0, 3)
        self._chart.ci.layout.setRowStretchFactor(1, 1)
        layout.addWidget(self._chart)

        controls = QHBoxLayout()

        self._rewind_button = QPushButton("-1min")
        self._rewind_button.clicked.connect(self._on_rewind_clicked)
        controls.addWidget(self._rewind_button)

        self._play_button = QPushButton("PLAY")
        self._play_button.clicked.connect(self._on_play_pause_clicked)
        controls.addWidget(self._play_button)

        self._advance_button = QPushButton("+1min")
        self._advance_button.clicked.connect(self._on_advance_clicked)
        controls.addWidget(self._advance_button)

        self._timeline_slider = QSlider(Qt.Horizontal)
        self._timeline_slider.setRange(0, self._total_minutes)
        self._timeline_slider.sliderReleased.connect(self._on_timeline_released)
        controls.addWidget(self._timeline_slider)

        layout.addLayout(controls)

        self.setCentralWidget(central)

        self._render_state(self.replay_engine.state)

    def _on_rewind_clicked(self) -> None:
        if self.replay_engine.current_time <= self._start_time:
            return

        self._render_state(self.replay_engine.rewind())

    def _on_advance_clicked(self) -> None:
        if self.replay_engine.current_time >= self._end_time:
            return

        self._render_state(self.replay_engine.advance())

    def _on_play_pause_clicked(self) -> None:
        if self._play_timer.isActive():
            self._play_timer.stop()
            self._play_button.setText("PLAY")
        else:
            self._play_timer.start()
            self._play_button.setText("PAUSE")

    def _on_play_tick(self) -> None:
        if self.replay_engine.current_time >= self._end_time:
            self._play_timer.stop()
            self._play_button.setText("PLAY")
            return

        self._render_state(self.replay_engine.advance())

    def _on_timeline_released(self) -> None:
        target_minutes = self._timeline_slider.value()
        target_time = self._start_time + (target_minutes * (self._end_time - self._start_time)
                                           / max(self._total_minutes, 1))
        self._render_state(self.replay_engine.seek(target_time))

    def _render_state(self, state) -> None:
        self._time_label.setText(f"Simulated time: {state.current_time.strftime('%Y-%m-%d %H:%M')}")

        candles = [
            (
                (bar["bar_start"] - self._start_time).total_seconds() / 60,
                bar["open"],
                bar["high"],
                bar["low"],
                bar["close"],
            )
            for bar in state.bars
        ]
        volumes = [
            (
                (bar["bar_start"] - self._start_time).total_seconds() / 60,
                bar["volume"],
                bar["close"] >= bar["open"],
            )
            for bar in state.bars
        ]

        self._price_plot.clear()
        self._price_plot.addItem(CandlestickItem(candles))

        self._volume_plot.clear()
        if volumes:
            self._volume_plot.addItem(
                pg.BarGraphItem(
                    x=[v[0] for v in volumes],
                    height=[v[1] for v in volumes],
                    width=0.7,
                    brushes=["g" if v[2] else "r" for v in volumes],
                )
            )

        elapsed_minutes = (state.current_time - self._start_time).total_seconds() / 60
        self._timeline_slider.blockSignals(True)
        self._timeline_slider.setValue(int(elapsed_minutes))
        self._timeline_slider.blockSignals(False)
