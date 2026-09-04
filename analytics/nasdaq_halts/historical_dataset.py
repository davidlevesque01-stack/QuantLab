from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Protocol

from shared.calendar.trading_calendar import get_session_close, get_trading_days

from .models import (
    AnalysisRequest,
    HistoricalHaltDataset,
    HistoricalHaltDay,
)


class CoreEpisodeSource(Protocol):
    """Minimal source contract required by the dataset builder.

    The concrete PostgreSQL implementation is intentionally not coupled
    to this module.
    """

    def fetch_core_episodes(
        self,
        ticker: str,
        start_date: date | None,
        end_date: date,
        reason_codes: tuple[str, ...],
    ) -> Iterable[dict]:
        ...


@dataclass(frozen=True)
class EpisodeView:
    trading_date: date
    start_time: datetime
    end_time: datetime | None
    reason_code: str


def build_historical_dataset(
    request: AnalysisRequest,
    episodes: Iterable[dict | EpisodeView],
) -> HistoricalHaltDataset:
    """Build the reusable Halt-Day dataset from qualified CORE episodes.

    Each episode is projected onto every NASDAQ trading session covered
    by the episode. Weekends and market holidays are excluded through
    the shared TradingCalendar.

    The dataset also retains the number of distinct CORE episodes that
    contribute to the requested analytical window.
    """

    req = request.normalized()
    start_date = _lookback_start(req)
    grouped: dict[date, list[dict | EpisodeView]] = defaultdict(list)
    core_episode_count = 0

    for episode in episodes:
        episode_start, episode_end = _episode_bounds(episode)

        if episode_start is None:
            continue

        first_date = episode_start.date()
        last_date = (
            episode_end.date()
            if episode_end is not None
            else first_date
        )

        if last_date < first_date:
            last_date = first_date

        episode_trading_days = get_trading_days(
            first_date,
            last_date,
        )

        included_dates = [
            trading_date
            for trading_date in episode_trading_days
            if (
                trading_date <= req.observation_date
                and (
                    start_date is None
                    or trading_date >= start_date
                )
            )
        ]

        if not included_dates:
            continue

        core_episode_count += 1

        for trading_date in included_dates:
            grouped[trading_date].append(episode)

    days = []

    if grouped:
        first_dataset_date = min(grouped)
        trading_dates = get_trading_days(
            first_dataset_date,
            req.observation_date,
        )
    else:
        trading_dates = ()

    for trading_date in trading_dates:
        rows = grouped.get(trading_date)

        if not rows:
            continue

        days.append(
            HistoricalHaltDay(
                trading_date=trading_date,
                episode_count=len(rows),
                halted_at_close=any(
                    _halted_at_close(row, trading_date)
                    for row in rows
                ),
            )
        )

    return HistoricalHaltDataset(
        ticker=req.ticker,
        start_date=start_date,
        end_date=req.observation_date,
        halt_days=tuple(days),
        core_episode_count=core_episode_count,
    )


def _lookback_start(request: AnalysisRequest) -> date | None:
    if request.lookback_months is None:
        return None

    year = request.observation_date.year
    month = request.observation_date.month - request.lookback_months

    while month <= 0:
        year -= 1
        month += 12

    import calendar

    day = min(
        request.observation_date.day,
        calendar.monthrange(year, month)[1],
    )

    return date(year, month, day)


def _episode_bounds(
    episode: dict | EpisodeView,
) -> tuple[datetime | None, datetime | None]:
    """Return the actual HALT start and end timestamps."""

    if isinstance(episode, EpisodeView):
        return episode.start_time, episode.end_time

    start = episode.get("halt_start") or episode.get("start_time")
    end = episode.get("halt_end") or episode.get("end_time")

    start = _to_datetime(start)
    end = _to_datetime(end)

    if start is None:
        trading_date = _episode_date(episode)

        if trading_date is not None:
            start = datetime.combine(
                trading_date,
                datetime.min.time(),
            )

    return start, end


def _episode_date(episode: dict | EpisodeView) -> date:
    if isinstance(episode, EpisodeView):
        return episode.trading_date

    value = episode.get("trading_date") or episode.get("date")

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return date.fromisoformat(str(value))


def _to_datetime(value) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, date):
        return datetime.combine(
            value,
            datetime.min.time(),
        )

    return datetime.fromisoformat(
        str(value).replace("Z", "+00:00")
    )


def _halted_at_close(
    episode: dict | EpisodeView,
    trading_date: date,
) -> bool:
    """Return whether an episode was still active at that session's close.

    The session close comes from the shared TradingCalendar, so normal
    sessions use 16:00 while early-close sessions use their actual close
    time.

    An episode is considered active at close when its valid end occurs
    strictly after the session close, or when no valid end exists.
    """

    session_close = get_session_close(trading_date)

    if session_close is None:
        return False

    if isinstance(episode, EpisodeView):
        end_time = episode.end_time
    else:
        if "halted_at_close" in episode:
            explicit_value = episode["halted_at_close"]

            if explicit_value is not None:
                return bool(explicit_value)

        end_time = episode.get("end_time") or episode.get("halt_end")

    end_time = _to_datetime(end_time)

    if end_time is None:
        return True

    session_close_datetime = datetime.combine(
        trading_date,
        session_close,
    )

    return end_time > session_close_datetime
