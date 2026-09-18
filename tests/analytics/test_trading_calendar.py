from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from shared.calendar.trading_calendar import (
    AFTER_HOURS_CLOSE,
    EARLY_CLOSE,
    NASDAQ_TZ,
    NORMAL_CLOSE,
    PRE_MARKET_OPEN,
    REGULAR_OPEN,
    SESSION_AFTER_HOURS,
    SESSION_PRE_MARKET,
    SESSION_REGULAR,
    classify_session,
    get_session_bounds,
    get_session_close,
    get_trading_days,
    is_trading_day,
    localize,
    to_nasdaq_local,
)


def test_weekend_is_not_trading_day():
    assert not is_trading_day(date(2026, 7, 4))
    assert not is_trading_day(date(2026, 7, 5))


def test_normal_weekday_is_trading_day():
    assert is_trading_day(date(2026, 7, 6))


def test_nasdaq_holiday_is_not_trading_day():
    assert not is_trading_day(date(2026, 7, 3))
    assert get_session_close(date(2026, 7, 3)) is None


def test_early_close_is_trading_day():
    assert is_trading_day(date(2026, 11, 27))
    assert get_session_close(date(2026, 11, 27)) == EARLY_CLOSE


def test_normal_close_is_1600():
    assert get_session_close(date(2026, 7, 6)) == NORMAL_CLOSE
    assert get_session_close(date(2026, 7, 6)) == time(16, 0)


def test_christmas_eve_is_early_close():
    assert is_trading_day(date(2026, 12, 24))
    assert get_session_close(date(2026, 12, 24)) == time(13, 0)


def test_historical_2020_independence_day():
    assert not is_trading_day(date(2020, 7, 3))


def test_historical_2020_christmas_eve():
    assert is_trading_day(date(2020, 12, 24))
    assert get_session_close(date(2020, 12, 24)) == time(13, 0)


def test_multiday_episode_excludes_weekend():
    days = get_trading_days(
        date(2020, 3, 12),
        date(2020, 3, 16),
    )

    assert days == (
        date(2020, 3, 12),
        date(2020, 3, 13),
        date(2020, 3, 16),
    )


def test_multiday_episode_excludes_holiday():
    days = get_trading_days(
        date(2020, 7, 2),
        date(2020, 7, 6),
    )

    assert days == (
        date(2020, 7, 2),
        date(2020, 7, 6),
    )


def test_session_bounds_normal_day():
    bounds = get_session_bounds(date(2026, 7, 6))

    assert bounds.pre_market_open == PRE_MARKET_OPEN
    assert bounds.regular_open == REGULAR_OPEN
    assert bounds.regular_close == NORMAL_CLOSE
    assert bounds.after_hours_close == AFTER_HOURS_CLOSE


def test_session_bounds_early_close_day():
    bounds = get_session_bounds(date(2026, 12, 24))

    assert bounds.regular_close == EARLY_CLOSE
    assert bounds.after_hours_close == AFTER_HOURS_CLOSE


def test_session_bounds_non_trading_day_is_none():
    assert get_session_bounds(date(2026, 7, 4)) is None


def test_localize_attaches_nasdaq_timezone():
    naive = datetime(2026, 8, 14, 10, 17, 0)

    localized = localize(naive)

    assert localized.tzinfo == NASDAQ_TZ
    assert localized.replace(tzinfo=None) == naive


def test_localize_rejects_already_aware_datetime():
    aware = datetime(2026, 8, 14, 10, 17, 0, tzinfo=ZoneInfo("UTC"))

    with pytest.raises(ValueError):
        localize(aware)


def test_to_nasdaq_local_rejects_naive_datetime():
    naive = datetime(2026, 8, 14, 10, 17, 0)

    with pytest.raises(ValueError):
        to_nasdaq_local(naive)


def test_to_nasdaq_local_round_trips_with_localize_summer():
    # EDT (UTC-4) -- 2026-08-14 is in daylight saving time.
    naive = datetime(2026, 8, 14, 10, 17, 0)
    aware_utc = localize(naive).astimezone(ZoneInfo("UTC"))

    assert to_nasdaq_local(aware_utc) == naive


def test_to_nasdaq_local_round_trips_with_localize_winter():
    # EST (UTC-5) -- 2026-01-14 is outside daylight saving time.
    naive = datetime(2026, 1, 14, 10, 17, 0)
    aware_utc = localize(naive).astimezone(ZoneInfo("UTC"))

    assert to_nasdaq_local(aware_utc) == naive


def test_classify_session_boundaries():
    bounds = get_session_bounds(date(2026, 7, 6))

    assert classify_session(datetime(2026, 7, 6, 4, 0), bounds) == SESSION_PRE_MARKET
    assert classify_session(datetime(2026, 7, 6, 9, 29), bounds) == SESSION_PRE_MARKET
    assert classify_session(datetime(2026, 7, 6, 9, 30), bounds) == SESSION_REGULAR
    assert classify_session(datetime(2026, 7, 6, 15, 59), bounds) == SESSION_REGULAR
    assert classify_session(datetime(2026, 7, 6, 16, 0), bounds) == SESSION_AFTER_HOURS
    assert classify_session(datetime(2026, 7, 6, 19, 59), bounds) == SESSION_AFTER_HOURS


def test_classify_session_raises_outside_window():
    bounds = get_session_bounds(date(2026, 7, 6))

    with pytest.raises(ValueError):
        classify_session(datetime(2026, 7, 6, 3, 59), bounds)

    with pytest.raises(ValueError):
        classify_session(datetime(2026, 7, 6, 20, 0), bounds)
