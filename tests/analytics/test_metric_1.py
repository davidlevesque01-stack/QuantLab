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


def test_metric_1_observation_day_is_included():
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

    assert result.metric_1 == 2


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


def test_metric_2_no_halt_days():
    result = AnalysisService().analyze(_request(), episodes=[])

    assert result.metric_1 == 0
    assert result.metric_2 == "N/A"


def test_metric_2_one_episode_one_halt_day():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 10, 30),
            "halt_end": datetime(2026, 8, 27, 10, 35),
            "end_time": datetime(2026, 8, 27, 10, 35),
        }
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_1 == 1
    assert result.metric_2 == 1.0


def test_metric_2_three_episodes_over_two_halt_days():
    episodes = [
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 9, 0),
            "halt_end": datetime(2026, 8, 25, 9, 5),
            "end_time": datetime(2026, 8, 25, 9, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 10, 0),
            "halt_end": datetime(2026, 8, 25, 10, 5),
            "end_time": datetime(2026, 8, 25, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 26),
            "halt_start": datetime(2026, 8, 26, 11, 0),
            "halt_end": datetime(2026, 8, 26, 11, 5),
            "end_time": datetime(2026, 8, 26, 11, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_1 == 2
    assert result.metric_2 == 1.5


def test_metric_2_multiday_episode_counts_one_core_episode():
    episodes = [
        {
            "trading_date": date(2020, 3, 12),
            "halt_start": datetime(2020, 3, 12, 11, 18, 33),
            "halt_end": datetime(2020, 3, 16, 9, 45, 2),
            "end_time": datetime(2020, 3, 16, 9, 45, 2),
        },
    ]

    request = AnalysisRequest(
        ticker="TESS",
        observation_date=date(2020, 3, 16),
        lookback_months=None,
        reason_codes=("LUDP",),
    )

    result = AnalysisService().analyze(
        request,
        episodes=episodes,
    )

    assert result.metric_1 == 3
    assert result.metric_2 == 1 / 3


def test_metric_3_no_halt_days():
    result = AnalysisService().analyze(_request(), episodes=[])

    assert result.metric_1 == 0
    assert result.metric_2 == "N/A"
    assert result.metric_3 == "N/A"


def test_metric_3_halt_on_observation_day():
    episodes = [
        {
            "trading_date": OBSERVATION_DATE,
            "halt_start": datetime(2026, 8, 28, 10, 0),
            "halt_end": datetime(2026, 8, 28, 10, 5),
            "end_time": datetime(2026, 8, 28, 10, 5),
        }
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_3 == 0


def test_metric_3_halt_on_previous_calendar_day():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 10, 0),
            "halt_end": datetime(2026, 8, 27, 10, 5),
            "end_time": datetime(2026, 8, 27, 10, 5),
        }
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_3 == 1


def test_metric_3_uses_calendar_days_not_trading_days():
    episodes = [
        {
            "trading_date": date(2026, 8, 21),
            "halt_start": datetime(2026, 8, 21, 10, 0),
            "halt_end": datetime(2026, 8, 21, 10, 5),
            "end_time": datetime(2026, 8, 21, 10, 5),
        }
    ]

    request = AnalysisRequest(
        ticker="ABCD",
        observation_date=date(2026, 8, 24),
        lookback_months=None,
        reason_codes=("LUDP",),
    )

    result = AnalysisService().analyze(
        request,
        episodes=episodes,
    )

    assert result.metric_3 == 3


def test_metric_3_uses_most_recent_halt_day():
    episodes = [
        {
            "trading_date": date(2026, 8, 20),
            "halt_start": datetime(2026, 8, 20, 10, 0),
            "halt_end": datetime(2026, 8, 20, 10, 5),
            "end_time": datetime(2026, 8, 20, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 11, 0),
            "halt_end": datetime(2026, 8, 25, 11, 5),
            "end_time": datetime(2026, 8, 25, 11, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_3 == 3


def test_metric_5_no_halt_days():
    result = AnalysisService().analyze(_request(), episodes=[])

    assert result.metric_5 == "No"


def test_metric_5_single_halt_day():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 10, 0),
            "halt_end": datetime(2026, 8, 27, 10, 5),
            "end_time": datetime(2026, 8, 27, 10, 5),
        }
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_5 == "No"


def test_metric_5_consecutive_trading_days():
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 10, 0),
            "halt_end": datetime(2026, 8, 25, 10, 5),
            "end_time": datetime(2026, 8, 25, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_5 == "Yes"


def test_metric_5_weekend_does_not_break_sequence():
    # Friday -> Monday are consecutive trading sessions.
    episodes = [
        {
            "trading_date": date(2026, 8, 21),
            "halt_start": datetime(2026, 8, 21, 10, 0),
            "halt_end": datetime(2026, 8, 21, 10, 5),
            "end_time": datetime(2026, 8, 21, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_5 == "Yes"


def test_metric_5_intervening_trading_day_breaks_sequence():
    # Monday -> Wednesday: Tuesday is a trading session.
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 26),
            "halt_start": datetime(2026, 8, 26, 10, 0),
            "halt_end": datetime(2026, 8, 26, 10, 5),
            "end_time": datetime(2026, 8, 26, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_5 == "No"


def test_metric_6_no_sequential_blocks():
    result = AnalysisService().analyze(_request(), episodes=[])

    assert result.metric_5 == "No"
    assert result.metric_6 == 0


def test_metric_6_two_consecutive_halt_days():
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 10, 0),
            "halt_end": datetime(2026, 8, 25, 10, 5),
            "end_time": datetime(2026, 8, 25, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_5 == "Yes"
    assert result.metric_6 == 1


def test_metric_6_three_consecutive_halt_days_form_one_block():
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 10, 0),
            "halt_end": datetime(2026, 8, 25, 10, 5),
            "end_time": datetime(2026, 8, 25, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 26),
            "halt_start": datetime(2026, 8, 26, 10, 0),
            "halt_end": datetime(2026, 8, 26, 10, 5),
            "end_time": datetime(2026, 8, 26, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_5 == "Yes"
    assert result.metric_6 == 1


def test_metric_6_two_separate_blocks():
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 10, 0),
            "halt_end": datetime(2026, 8, 25, 10, 5),
            "end_time": datetime(2026, 8, 25, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 10, 0),
            "halt_end": datetime(2026, 8, 27, 10, 5),
            "end_time": datetime(2026, 8, 27, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 10, 0),
            "halt_end": datetime(2026, 8, 28, 10, 5),
            "end_time": datetime(2026, 8, 28, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_5 == "Yes"
    assert result.metric_6 == 2


def test_metric_6_weekend_does_not_split_block():
    episodes = [
        {
            "trading_date": date(2026, 8, 21),
            "halt_start": datetime(2026, 8, 21, 10, 0),
            "halt_end": datetime(2026, 8, 21, 10, 5),
            "end_time": datetime(2026, 8, 21, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_5 == "Yes"
    assert result.metric_6 == 1


def test_metric_6_intervening_trading_day_splits_blocks():
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 26),
            "halt_start": datetime(2026, 8, 26, 10, 0),
            "halt_end": datetime(2026, 8, 26, 10, 5),
            "end_time": datetime(2026, 8, 26, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_5 == "No"
    assert result.metric_6 == 0


def test_metric_7_no_sequential_blocks():
    result = AnalysisService().analyze(_request(), episodes=[])

    assert result.metric_7 == "N/A"


def test_metric_7_one_block_of_two_days():
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 10, 0),
            "halt_end": datetime(2026, 8, 25, 10, 5),
            "end_time": datetime(2026, 8, 25, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_7 == 2


def test_metric_7_three_day_block():
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 10, 0),
            "halt_end": datetime(2026, 8, 25, 10, 5),
            "end_time": datetime(2026, 8, 25, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 26),
            "halt_start": datetime(2026, 8, 26, 10, 0),
            "halt_end": datetime(2026, 8, 26, 10, 5),
            "end_time": datetime(2026, 8, 26, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_7 == 3


def test_metric_7_average_length_of_multiple_blocks():
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 10, 0),
            "halt_end": datetime(2026, 8, 25, 10, 5),
            "end_time": datetime(2026, 8, 25, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 10, 0),
            "halt_end": datetime(2026, 8, 27, 10, 5),
            "end_time": datetime(2026, 8, 27, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 10, 0),
            "halt_end": datetime(2026, 8, 28, 10, 5),
            "end_time": datetime(2026, 8, 28, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 31),
            "halt_start": datetime(2026, 8, 31, 10, 0),
            "halt_end": datetime(2026, 8, 31, 10, 5),
            "end_time": datetime(2026, 8, 31, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 31),
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    # Blocks: Mon-Tue = 2 days, Thu-Fri-Mon = 3 days.
    assert result.metric_7 == 2.5



def test_metric_9_no_halt_days():
    result = AnalysisService().analyze(_request(), episodes=[])

    assert result.metric_9 == 0


def test_metric_9_halt_ends_before_market_close():
    episodes = [
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 14, 0),
            "halt_end": datetime(2026, 8, 28, 15, 30),
            "end_time": datetime(2026, 8, 28, 15, 30),
        }
    ]

    result = AnalysisService().analyze(_request(), episodes=episodes)

    assert result.metric_9 == 0


def test_metric_9_halt_active_after_market_close():
    episodes = [
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 14, 0),
            "halt_end": datetime(2026, 8, 28, 16, 30),
            "end_time": datetime(2026, 8, 28, 16, 30),
        }
    ]

    result = AnalysisService().analyze(_request(), episodes=episodes)

    assert result.metric_9 == 1


def test_metric_9_halt_ending_exactly_at_close_is_not_at_close():
    episodes = [
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 14, 0),
            "halt_end": datetime(2026, 8, 28, 16, 0),
            "end_time": datetime(2026, 8, 28, 16, 0),
        }
    ]

    result = AnalysisService().analyze(_request(), episodes=episodes)

    assert result.metric_9 == 0


def test_metric_9_multiday_episode_counts_each_trading_day_at_close():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 14, 0),
            "halt_end": datetime(2026, 8, 31, 10, 0),
            "end_time": datetime(2026, 8, 31, 10, 0),
        }
    ]

    request = AnalysisRequest(
        ticker="ABCD",
        observation_date=date(2026, 8, 31),
        lookback_months=None,
        reason_codes=("LUDP",),
    )

    result = AnalysisService().analyze(request, episodes=episodes)

    # Thu 27 and Fri 28: halted at close.
    # Mon 31: resumed before close.
    assert result.metric_9 == 2


def test_metric_9_early_close_uses_calendar_close_time():
    episodes = [
        {
            "trading_date": date(2026, 11, 27),
            "halt_start": datetime(2026, 11, 27, 12, 0),
            "halt_end": datetime(2026, 11, 27, 13, 30),
            "end_time": datetime(2026, 11, 27, 13, 30),
        }
    ]

    request = AnalysisRequest(
        ticker="ABCD",
        observation_date=date(2026, 11, 27),
        lookback_months=None,
        reason_codes=("LUDP",),
    )

    result = AnalysisService().analyze(request, episodes=episodes)

    # The calendar supplies the early close for this session.
    assert result.metric_9 == 1


def test_metric_9_multiple_episodes_same_day_count_once():
    episodes = [
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 14, 0),
            "halt_end": datetime(2026, 8, 28, 16, 30),
            "end_time": datetime(2026, 8, 28, 16, 30),
        },
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 15, 0),
            "halt_end": datetime(2026, 8, 28, 17, 0),
            "end_time": datetime(2026, 8, 28, 17, 0),
        },
    ]

    result = AnalysisService().analyze(_request(), episodes=episodes)

    assert result.metric_9 == 1


def test_metric_9_observation_day_is_included():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 14, 0),
            "halt_end": datetime(2026, 8, 28, 16, 30),
            "end_time": datetime(2026, 8, 28, 16, 30),
        }
    ]

    result = AnalysisService().analyze(_request(), episodes=episodes)

    assert result.metric_9 == 2



def test_metric_1_multiple_halt_days():
    episodes = [
        {
            "trading_date": date(2026, 6, 8),
            "end_time": datetime(2026, 6, 8, 15, 22),
        },
        {
            "trading_date": date(2026, 7, 6),
            "end_time": datetime(2026, 7, 6, 9, 46),
        },
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="HKIT",
            observation_date=date(2026, 7, 6),
            lookback_months=1,
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    assert result.metric_1 == 2


def test_metric_1_multiple_halt_days_and_multiple_episodes_same_day():
    episodes = [
        {
            "trading_date": date(2026, 6, 8),
            "end_time": datetime(2026, 6, 8, 15, 22),
        },
        {
            "trading_date": date(2026, 7, 6),
            "end_time": datetime(2026, 7, 6, 9, 46),
        },
        {
            "trading_date": date(2026, 7, 6),
            "end_time": datetime(2026, 7, 6, 10, 30),
        },
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="HKIT",
            observation_date=date(2026, 7, 6),
            lookback_months=1,
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    assert result.metric_1 == 2


def test_metric_1_multiday_episode_counts_trading_sessions_only():
    episodes = [
        {
            "trading_date": date(2020, 3, 12),
            "halt_start": datetime(2020, 3, 12, 11, 18, 33),
            "halt_end": datetime(2020, 3, 16, 9, 45, 2),
            "end_time": datetime(2020, 3, 16, 9, 45, 2),
        },
    ]

    request = AnalysisRequest(
        ticker="TESS",
        observation_date=date(2020, 3, 16),
        lookback_months=None,
        reason_codes=("LUDP",),
    )

    result = AnalysisService().analyze(request, episodes=episodes)

    assert result.metric_1 == 3

def test_metric_8_no_sequential_blocks():
    result = AnalysisService().analyze(_request(), episodes=[])

    assert result.metric_8 == "N/A"


def test_metric_8_one_block_of_two_days():
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 10, 0),
            "halt_end": datetime(2026, 8, 25, 10, 5),
            "end_time": datetime(2026, 8, 25, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    assert result.metric_8 == 2


def test_metric_8_returns_longest_block():
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 10, 0),
            "halt_end": datetime(2026, 8, 25, 10, 5),
            "end_time": datetime(2026, 8, 25, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 10, 0),
            "halt_end": datetime(2026, 8, 27, 10, 5),
            "end_time": datetime(2026, 8, 27, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 10, 0),
            "halt_end": datetime(2026, 8, 28, 10, 5),
            "end_time": datetime(2026, 8, 28, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        _request(),
        episodes=episodes,
    )

    # Blocks: Mon-Tue = 2 days, Thu-Fri = 2 days.
    assert result.metric_8 == 2


def test_metric_8_longest_of_two_and_three_day_blocks():
    episodes = [
        {
            "trading_date": date(2026, 8, 24),
            "halt_start": datetime(2026, 8, 24, 10, 0),
            "halt_end": datetime(2026, 8, 24, 10, 5),
            "end_time": datetime(2026, 8, 24, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 25),
            "halt_start": datetime(2026, 8, 25, 10, 0),
            "halt_end": datetime(2026, 8, 25, 10, 5),
            "end_time": datetime(2026, 8, 25, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 10, 0),
            "halt_end": datetime(2026, 8, 27, 10, 5),
            "end_time": datetime(2026, 8, 27, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 10, 0),
            "halt_end": datetime(2026, 8, 28, 10, 5),
            "end_time": datetime(2026, 8, 28, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 31),
            "halt_start": datetime(2026, 8, 31, 10, 0),
            "halt_end": datetime(2026, 8, 31, 10, 5),
            "end_time": datetime(2026, 8, 31, 10, 5),
        },
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 31),
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    # Blocks: Mon-Tue = 2 days, Thu-Fri-Mon = 3 days.
    assert result.metric_8 == 3
from datetime import date, datetime

from analytics.nasdaq_halts.analysis_service import AnalysisService
from analytics.nasdaq_halts.models import AnalysisRequest


def test_metric_10_no_halt_on_observation_day():
    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 28),
            lookback_months=None,
            reason_codes=("LUDP",),
        ),
        episodes=[],
    )

    assert result.metric_10 == "No"


def test_metric_10_halt_on_observation_day():
    episodes = [
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 10, 0),
            "halt_end": datetime(2026, 8, 28, 10, 5),
            "end_time": datetime(2026, 8, 28, 10, 5),
        }
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 28),
            lookback_months=None,
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    assert result.metric_10 == "Yes"


def test_metric_10_halt_on_previous_day_only():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 10, 0),
            "halt_end": datetime(2026, 8, 27, 10, 5),
            "end_time": datetime(2026, 8, 27, 10, 5),
        }
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 28),
            lookback_months=None,
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    assert result.metric_10 == "No"


def test_metric_10_multiday_episode_active_on_observation_day():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 14, 0),
            "halt_end": datetime(2026, 8, 28, 10, 0),
            "end_time": datetime(2026, 8, 28, 10, 0),
        }
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 28),
            lookback_months=None,
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    assert result.metric_10 == "Yes"


def test_metric_10_multiple_halts_same_observation_day():
    episodes = [
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 10, 0),
            "halt_end": datetime(2026, 8, 28, 10, 5),
            "end_time": datetime(2026, 8, 28, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 11, 0),
            "halt_end": datetime(2026, 8, 28, 11, 5),
            "end_time": datetime(2026, 8, 28, 11, 5),
        },
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 28),
            lookback_months=None,
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    assert result.metric_10 == "Yes"

def test_metric_11_no_halt_on_observation_day():
    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 28),
            lookback_months=None,
            reason_codes=("LUDP",),
        ),
        episodes=[],
    )

    assert result.metric_10 == "No"
    assert result.metric_11 == 0


def test_metric_11_one_halt_on_observation_day():
    episodes = [
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 10, 0),
            "halt_end": datetime(2026, 8, 28, 10, 5),
            "end_time": datetime(2026, 8, 28, 10, 5),
        }
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 28),
            lookback_months=None,
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    assert result.metric_10 == "Yes"
    assert result.metric_11 == 1


def test_metric_11_two_distinct_core_episodes_on_observation_day():
    episodes = [
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 10, 0),
            "halt_end": datetime(2026, 8, 28, 10, 5),
            "end_time": datetime(2026, 8, 28, 10, 5),
        },
        {
            "trading_date": date(2026, 8, 28),
            "halt_start": datetime(2026, 8, 28, 11, 0),
            "halt_end": datetime(2026, 8, 28, 11, 5),
            "end_time": datetime(2026, 8, 28, 11, 5),
        },
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 28),
            lookback_months=None,
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    assert result.metric_10 == "Yes"
    assert result.metric_11 == 2


def test_metric_11_previous_day_only_returns_zero():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 10, 0),
            "halt_end": datetime(2026, 8, 27, 10, 5),
            "end_time": datetime(2026, 8, 27, 10, 5),
        }
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 28),
            lookback_months=None,
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    assert result.metric_10 == "No"
    assert result.metric_11 == 0


def test_metric_11_multiday_episode_active_on_observation_day():
    episodes = [
        {
            "trading_date": date(2026, 8, 27),
            "halt_start": datetime(2026, 8, 27, 14, 0),
            "halt_end": datetime(2026, 8, 28, 10, 0),
            "end_time": datetime(2026, 8, 28, 10, 0),
        }
    ]

    result = AnalysisService().analyze(
        AnalysisRequest(
            ticker="ABCD",
            observation_date=date(2026, 8, 28),
            lookback_months=None,
            reason_codes=("LUDP",),
        ),
        episodes=episodes,
    )

    assert result.metric_10 == "Yes"
    assert result.metric_11 == 1
