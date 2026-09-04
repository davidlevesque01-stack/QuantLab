from __future__ import annotations

from datetime import date

from shared.calendar.trading_calendar import get_trading_days

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

    Metric 2
    -------
    Average HALTs per Halt Day.

    Metric 3
    -------
    Calendar days since the most recent Halt Day.

    Metric 4
    -------
    Average calendar days between consecutive distinct Halt Days.

    Metric 5
    -------
    Whether at least two consecutive trading sessions contain
    a qualifying Halt Day.

    Metrics 6-11 remain intentionally unimplemented.
    """

    metric_1 = dataset.halt_day_count

    metric_2 = (
        dataset.core_episode_count / metric_1
        if metric_1 > 0
        else "N/A"
    )

    metric_3 = (
        (observation_date - dataset.halt_days[-1].trading_date).days
        if dataset.halt_days
        else "N/A"
    )

    if metric_1 < 2:
        metric_4 = "N/A"
    else:
        halt_dates = [
            halt_day.trading_date
            for halt_day in dataset.halt_days
        ]

        intervals = [
            (current - previous).days
            for previous, current in zip(
                halt_dates,
                halt_dates[1:],
            )
        ]

        metric_4 = sum(intervals) / len(intervals)

    sequential_blocks = _build_sequential_blocks(dataset)

    metric_5 = "Yes" if sequential_blocks else "No"
    metric_6 = len(sequential_blocks)

    metric_7 = (
        sum(len(block) for block in sequential_blocks)
        / len(sequential_blocks)
        if sequential_blocks
        else "N/A"
    )

    metric_8 = (
        max(len(block) for block in sequential_blocks)
        if sequential_blocks
        else "N/A"
    )

    metric_9 = dataset.halt_at_close_day_count

    observation_day = next(
        (
            halt_day
            for halt_day in dataset.halt_days
            if halt_day.trading_date == observation_date
        ),
        None,
    )

    metric_10 = "Yes" if observation_day is not None else "No"

    metric_11 = (
        observation_day.episode_count
        if observation_day is not None
        else 0
    )

    return AnalysisResult(
        ticker=dataset.ticker,
        observation_date=observation_date,
        lookback_start=dataset.start_date,
        lookback_end=dataset.end_date,
        reason_codes=reason_codes,
        metric_1=metric_1,
        metric_2=metric_2,
        metric_3=metric_3,
        metric_4=metric_4,
        metric_5=metric_5,
        metric_6=metric_6,
        metric_7=metric_7,
        metric_8=metric_8,
        metric_9=metric_9,
        metric_10=metric_10,
        metric_11=metric_11,
    )


def _build_sequential_blocks(
    dataset: HistoricalHaltDataset,
) -> list[list[date]]:
    """Build distinct sequential Halt-Day blocks.

    A block contains at least two Halt Days occurring on consecutive
    market trading sessions. Weekends and market holidays therefore do
    not break a block.
    """

    halt_dates = sorted(
        {
            halt_day.trading_date
            for halt_day in dataset.halt_days
        }
    )

    if len(halt_dates) < 2:
        return []

    blocks: list[list[date]] = []
    current_block = [halt_dates[0]]

    for current_date in halt_dates[1:]:
        previous_date = current_block[-1]

        sessions = get_trading_days(
            previous_date,
            current_date,
        )

        if len(sessions) == 2:
            current_block.append(current_date)
        else:
            if len(current_block) >= 2:
                blocks.append(current_block)

            current_block = [current_date]

    if len(current_block) >= 2:
        blocks.append(current_block)

    return blocks
