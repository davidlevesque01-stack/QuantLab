from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Protocol

from .models import (
    AnalysisRequest,
    HistoricalHaltDataset,
    HistoricalHaltDay,
)


class CoreEpisodeSource(Protocol):
    """Minimal source contract required by the dataset builder.

    The concrete PostgreSQL implementation is intentionally not coupled
    to this module in 22.6.2.
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
    """Build the reusable Halt-Day dataset from already-qualified episodes.

    No Metric 1-11 formula is implemented here. This layer only normalizes
    episodes into distinct historical trading days.
    """

    req = request.normalized()
    start_date = _lookback_start(req)
    grouped: dict[date, list[dict | EpisodeView]] = defaultdict(list)

    for episode in episodes:
        trading_date = _episode_date(episode)
        if trading_date > req.observation_date:
            continue
        if start_date is not None and trading_date < start_date:
            continue
        grouped[trading_date].append(episode)

    days = []
    for trading_date in sorted(grouped):
        rows = grouped[trading_date]
        days.append(
            HistoricalHaltDay(
                trading_date=trading_date,
                episode_count=len(rows),
                halted_at_close=any(_halted_at_close(row) for row in rows),
            )
        )

    end_date = req.observation_date
    return HistoricalHaltDataset(
        ticker=req.ticker,
        start_date=start_date,
        end_date=end_date,
        halt_days=tuple(days),
    )


def _lookback_start(request: AnalysisRequest) -> date | None:
    if request.lookback_months is None:
        return None

    year = request.observation_date.year
    month = request.observation_date.month - request.lookback_months
    while month <= 0:
        year -= 1
        month += 12

    # Preserve the day when possible; clamp to the last day of the month.
    import calendar

    day = min(
        request.observation_date.day,
        calendar.monthrange(year, month)[1],
    )
    return date(year, month, day)


def _episode_date(episode: dict | EpisodeView) -> date:
    if isinstance(episode, EpisodeView):
        return episode.trading_date

    value = episode.get("trading_date") or episode.get("date")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _halted_at_close(episode: dict | EpisodeView) -> bool:
    if isinstance(episode, EpisodeView):
        end_time = episode.end_time
    else:
        if "halted_at_close" in episode:
            return bool(episode["halted_at_close"])
        end_time = episode.get("end_time") or episode.get("halt_end")

    if end_time is None:
        return True

    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

    # This is only a provisional dataset flag. The final Metric 9
    # implementation will apply the approved ET/session rules explicitly.
    return end_time.hour >= 16
