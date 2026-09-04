from datetime import datetime

from collectors.nasdaq_halts.src.nasdaq_episodes import build_halt_episodes


def test_same_halt_start_keeps_latest_valid_resumption():
    events = [
        {
            "symbol": "TESS",
            "market": "NASDAQ",
            "reason_code": "LUDP",
            "halt_start": datetime(2020, 3, 12, 11, 18, 33),
            "halt_end": datetime(2020, 3, 12, 11, 23, 33),
        },
        {
            "symbol": "TESS",
            "market": "NASDAQ",
            "reason_code": "LUDP",
            "halt_start": datetime(2020, 3, 12, 11, 18, 33),
            "halt_end": datetime(2020, 3, 16, 9, 45, 2),
        },
    ]

    episodes, _ = build_halt_episodes(events)

    assert len(episodes) == 1

    episode = episodes[0]

    assert episode["symbol"] == "TESS"
    assert episode["reason_code"] == "LUDP"
    assert episode["halt_start"] == datetime(2020, 3, 12, 11, 18, 33)
    assert episode["halt_end"] == datetime(2020, 3, 16, 9, 45, 2)
    assert episode["halt_at_close"] == "MULTI_DAY"
