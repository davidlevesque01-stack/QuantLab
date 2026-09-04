from datetime import date, datetime

from analytics.nasdaq_halts.analysis_service import AnalysisService
from analytics.nasdaq_halts.models import AnalysisRequest


def test_request_normalization():
    request = AnalysisRequest(
        ticker="  abcd ",
        observation_date=date(2026, 8, 28),
        reason_codes=("LUDP", " M "),
    ).normalized()

    assert request.ticker == "ABCD"
    assert request.lookback_months == 36
    assert request.reason_codes == ("LUDP", "M")


def test_historical_data_includes_observation_day():
    request = AnalysisRequest(
        ticker="ABCD",
        observation_date=date(2026, 8, 28),
    )

    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "end_time": datetime(2026, 8, 27, 16, 1),
        },
        {
            "trading_date": date(2026, 8, 28),
            "end_time": datetime(2026, 8, 28, 16, 1),
        },
        {
            "trading_date": date(2026, 8, 29),
            "end_time": datetime(2026, 8, 29, 16, 1),
        },
    ]

    result = AnalysisService().analyze(request, episodes=episodes)

    assert result.lookback_end == date(2026, 8, 28)
    assert result.metric_1 == 2


def test_results_contract_contains_all_metrics():
    request = AnalysisRequest(
        ticker="ABCD",
        observation_date=date(2026, 8, 28),
    )

    result = AnalysisService().analyze(request, episodes=[])

    values = result.as_dict()

    assert list(values) == [f"Metric {i}" for i in range(1, 12)]
    assert len(values) == 11

def test_historical_dataset_expands_multiday_episode_into_trading_days():
    from datetime import datetime

    from analytics.nasdaq_halts.historical_dataset import (
        build_historical_dataset,
    )

    request = AnalysisRequest(
        ticker="TESS",
        observation_date=date(2020, 3, 16),
        reason_codes=("LUDP",),
    )

    episodes = [
        {
            "trading_date": date(2020, 3, 12),
            "halt_start": datetime(2020, 3, 12, 11, 18, 33),
            "halt_end": datetime(2020, 3, 16, 9, 45, 2),
        }
    ]

    dataset = build_historical_dataset(request, episodes)

    assert tuple(
        day.trading_date
        for day in dataset.halt_days
    ) == (
        date(2020, 3, 12),
        date(2020, 3, 13),
        date(2020, 3, 16),
    )

    assert tuple(
        day.episode_count
        for day in dataset.halt_days
    ) == (1, 1, 1)
