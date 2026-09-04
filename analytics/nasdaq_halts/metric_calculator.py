from __future__ import annotations

from .models import AnalysisResult, HistoricalHaltDataset


def calculate_metrics(
    dataset: HistoricalHaltDataset,
    *,
    observation_date,
    reason_codes: tuple[str, ...],
) -> AnalysisResult:
    """Placeholder metric layer for 22.6.2.

    Metrics 1-11 are deliberately not calculated yet. Their exact formulas
    will be implemented in subsequent steps against the approved specification.
    """

    return AnalysisResult(
        ticker=dataset.ticker,
        observation_date=observation_date,
        lookback_start=dataset.start_date,
        lookback_end=dataset.end_date,
        reason_codes=reason_codes,
    )
