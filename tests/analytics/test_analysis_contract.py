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
