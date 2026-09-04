from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class AnalysisRequest:
    """Input contract for one Nasdaq HALT analysis."""

    ticker: str
    observation_date: date
    lookback_months: int | None = 36
    reason_codes: tuple[str, ...] = ("LUDP",)

    def normalized(self) -> "AnalysisRequest":
        ticker = self.ticker.strip().upper()
        reasons = tuple(
            code.strip().upper()
            for code in self.reason_codes
            if code and code.strip()
        )

        if not ticker:
            raise ValueError("ticker is required")
        if not reasons:
            raise ValueError("at least one reason code is required")
        if self.lookback_months is not None and self.lookback_months <= 0:
            raise ValueError("lookback_months must be positive or None")

        return AnalysisRequest(
            ticker=ticker,
            observation_date=self.observation_date,
            lookback_months=self.lookback_months,
            reason_codes=reasons,
        )


@dataclass(frozen=True)
class HistoricalHaltDay:
    """Reusable historical observation derived from qualified CORE episodes."""

    trading_date: date
    episode_count: int
    halted_at_close: bool


@dataclass(frozen=True)
class HistoricalHaltDataset:
    """Historical data prepared once and reused by Metrics 1-9."""

    ticker: str
    start_date: date | None
    end_date: date | None
    halt_days: tuple[HistoricalHaltDay, ...]

    @property
    def halt_day_count(self) -> int:
        return len(self.halt_days)

    @property
    def halt_at_close_day_count(self) -> int:
        return sum(day.halted_at_close for day in self.halt_days)


@dataclass(frozen=True)
class AnalysisResult:
    """Output contract for one observation.

    Metric calculation is intentionally not implemented in 22.6.2.
    Values therefore remain None until the metric layer is connected.
    """

    ticker: str
    observation_date: date
    lookback_start: date | None
    lookback_end: date
    reason_codes: tuple[str, ...]

    metric_1: Any = None
    metric_2: Any = None
    metric_3: Any = None
    metric_4: Any = None
    metric_5: Any = None
    metric_6: Any = None
    metric_7: Any = None
    metric_8: Any = None
    metric_9: Any = None
    metric_10: Any = None
    metric_11: Any = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "Metric 1": self.metric_1,
            "Metric 2": self.metric_2,
            "Metric 3": self.metric_3,
            "Metric 4": self.metric_4,
            "Metric 5": self.metric_5,
            "Metric 6": self.metric_6,
            "Metric 7": self.metric_7,
            "Metric 8": self.metric_8,
            "Metric 9": self.metric_9,
            "Metric 10": self.metric_10,
            "Metric 11": self.metric_11,
        }
