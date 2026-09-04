from datetime import date, time

from shared.calendar.trading_calendar import (
    EARLY_CLOSE,
    NORMAL_CLOSE,
    get_session_close,
    get_trading_days,
    is_trading_day,
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
