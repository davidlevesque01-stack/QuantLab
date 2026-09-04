from datetime import date, datetime

from analytics.nasdaq_halts.analysis_service import AnalysisService
from analytics.nasdaq_halts.models import AnalysisRequest


OBSERVATION_DATE = date(2026, 8, 28)


def _request():
    return AnalysisRequest(
        ticker="ABCD",
        observation_date=OBSERVATION_DATE,
        reason_codes=("LUDP",),
    )


def test_metric_1_no_halt_days():
    result = AnalysisService().analyze(_request(), episodes=[])

    assert result.metric_1 == 0


def test_metric_1_one_halt_day():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "end_time": datetime(2026, 8, 27, 10, 30),
        }
    ]

    result = AnalysisService().analyze(_request(), episodes=episodes)

    assert result.metric_1 == 1


def test_metric_1_multiple_episodes_same_day_count_once():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "end_time": datetime(2026, 8, 27, 10, 30),
        },
        {
            "trading_date": date(2026, 8, 27),
            "end_time": datetime(2026, 8, 27, 11, 45),
        },
        {
            "trading_date": date(2026, 8, 26),
            "end_time": datetime(2026, 8, 26, 14, 0),
        },
    ]

    result = AnalysisService().analyze(_request(), episodes=episodes)

    assert result.metric_1 == 2


def test_metric_1_observation_day_is_excluded():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "end_time": datetime(2026, 8, 27, 10, 30),
        },
        {
            "trading_date": OBSERVATION_DATE,
            "end_time": datetime(2026, 8, 28, 10, 30),
        },
    ]

    result = AnalysisService().analyze(_request(), episodes=episodes)

    assert result.metric_1 == 1


def test_metric_1_is_distinct_by_trading_date():
    episodes = [
        {
            "trading_date": date(2026, 8, 25),
            "end_time": datetime(2026, 8, 25, 9, 0),
        },
        {
            "trading_date": date(2026, 8, 25),
            "end_time": datetime(2026, 8, 25, 12, 0),
        },
        {
            "trading_date": date(2026, 8, 26),
            "end_time": datetime(2026, 8, 26, 9, 0),
        },
        {
            "trading_date": date(2026, 8, 27),
            "end_time": datetime(2026, 8, 27, 15, 0),
        },
    ]

    result = AnalysisService().analyze(_request(), episodes=episodes)

    assert result.metric_1 == 3


def test_metrics_2_to_11_remain_unimplemented():
    result = AnalysisService().analyze(_request(), episodes=[])

    assert result.metric_1 == 0
    for number in range(2, 12):
        assert getattr(result, f"metric_{number}") is None
