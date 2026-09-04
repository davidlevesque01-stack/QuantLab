from __future__ import annotations

from datetime import date

from .models import AnalysisResult, HistoricalHaltDataset


def calculate_metrics(
    dataset: HistoricalHaltDataset,
    *,
    observation_date: date,
    reason_codes: tuple[str, ...],
) -> AnalysisResult:
    """Calculate the metrics currently implemented by the analytics layer.

    Metric 1
    -------
    Number of distinct Halt Days in the historical observation window.

    The HistoricalHaltDataset is already restricted to dates strictly before
    the observation date and already represents each trading day only once.
    Therefore Metric 1 is simply the number of rows in ``halt_days``.

    Metrics 2-11 remain intentionally unimplemented in 22.6.3.
    """

    metric_1 = dataset.halt_day_count

    return AnalysisResult(
        ticker=dataset.ticker,
        observation_date=observation_date,
        lookback_start=dataset.start_date,
        lookback_end=dataset.end_date,
        reason_codes=reason_codes,
        metric_1=metric_1,
    )
