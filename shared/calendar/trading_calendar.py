from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


NORMAL_CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)
PRE_MARKET_OPEN = time(4, 0)
REGULAR_OPEN = time(9, 30)
AFTER_HOURS_CLOSE = time(20, 0)

# All naive timestamps persisted by QuantLab (Nasdaq HALT episodes, SEC filing
# dates, and market_bar_1m once BT-01 lands) represent Nasdaq's local wall-clock
# time, not UTC. This is the single source of truth for that convention -- see
# docs/architecture.md Section 22 and docs/database.md Section 15.
NASDAQ_TZ = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class SessionBounds:
    pre_market_open: time
    regular_open: time
    regular_close: time
    after_hours_close: time


def localize(naive_dt: datetime) -> datetime:
    """Attach the Nasdaq exchange timezone to a naive QuantLab timestamp.

    Raises ValueError if `naive_dt` already carries tzinfo, since a QuantLab
    timestamp is never expected to be tz-aware before this call -- silently
    re-localizing an already-aware value would risk a double conversion.
    """

    if naive_dt.tzinfo is not None:
        raise ValueError("localize() expects a naive datetime (no tzinfo)")

    return naive_dt.replace(tzinfo=NASDAQ_TZ)


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (occurrence - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last_day = calendar.monthrange(year, month)[1]
    last = date(year, month, last_day)
    offset = (last.weekday() - weekday) % 7
    return last - timedelta(days=offset)


def _observed_fixed_date(year: int, month: int, day: int) -> date:
    actual = date(year, month, day)

    if actual.weekday() == 5:
        return actual - timedelta(days=1)

    if actual.weekday() == 6:
        return actual + timedelta(days=1)

    return actual


def _closed_days(year: int) -> set[date]:
    closed = {
        _observed_fixed_date(year, 1, 1),
        _nth_weekday(year, 1, 0, 3),   # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),   # Presidents Day
        _last_weekday(year, 5, 0),     # Memorial Day
        _nth_weekday(year, 9, 0, 1),   # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed_fixed_date(year, 12, 25),
    }

    # Good Friday
    # Anonymous Gregorian computus.
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    easter = date(year, month, day)
    closed.add(easter - timedelta(days=2))

    # Juneteenth became a Nasdaq U.S. equity market holiday in 2022.
    if year >= 2022:
        closed.add(_observed_fixed_date(year, 6, 19))

    # Independence Day.
    # Nasdaq closes the U.S. equity market on the observed date.
    closed.add(_observed_fixed_date(year, 7, 4))

    return closed


def _early_close_days(year: int) -> set[date]:
    days = {
        _nth_weekday(year, 11, 3, 4) + timedelta(days=1),  # Friday after Thanksgiving
        date(year, 12, 24),                                # Christmas Eve
    }

    # Independence Day: when July 4 falls on Saturday/Sunday, the
    # observed date is a full closure. Otherwise July 3 is normally
    # an early-close session.
    july_3 = date(year, 7, 3)
    july_4 = date(year, 7, 4)

    if july_4.weekday() not in (5, 6):
        days.add(july_3)

    # Early-close days cannot also be full closures.
    days -= _closed_days(year)

    return days


def is_trading_day(day: date) -> bool:
    if day.weekday() >= 5:
        return False

    return day not in _closed_days(day.year)


def get_session_close(day: date) -> time | None:
    if not is_trading_day(day):
        return None

    if day in _early_close_days(day.year):
        return EARLY_CLOSE

    return NORMAL_CLOSE


def get_session_bounds(day: date) -> SessionBounds | None:
    regular_close = get_session_close(day)
    if regular_close is None:
        return None

    return SessionBounds(
        pre_market_open=PRE_MARKET_OPEN,
        regular_open=REGULAR_OPEN,
        regular_close=regular_close,
        after_hours_close=AFTER_HOURS_CLOSE,
    )


def get_trading_days(start_date: date, end_date: date) -> tuple[date, ...]:
    if end_date < start_date:
        return ()

    days: list[date] = []
    current = start_date

    while current <= end_date:
        if is_trading_day(current):
            days.append(current)
        current += timedelta(days=1)

    return tuple(days)
