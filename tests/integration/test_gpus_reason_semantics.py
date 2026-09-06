from __future__ import annotations

from datetime import date, datetime

from analytics.nasdaq_halts.core_source import NasdaqHaltCoreSource


def test_gpus_halt_reason_is_h11_and_not_t3():
    """Validate GPUS HALT-vs-resumption reason semantics against DEV CORE."""

    source = NasdaqHaltCoreSource()

    h11_rows = source.fetch_core_episodes(
        ticker="GPUS",
        start_date=date(2026, 8, 14),
        end_date=date(2026, 8, 25),
        reason_codes=("H11",),
    )

    assert len(h11_rows) == 1

    episode = h11_rows[0]

    assert episode["symbol"] == "GPUS"
    assert episode["reason_code"] == "H11"
    assert episode["halt_start"] == datetime(
        2026,
        8,
        14,
        14,
        15,
        13,
        698000,
    )
    assert episode["halt_end"] == datetime(
        2026,
        8,
        25,
        9,
        0,
        0,
    )
    assert float(episode["duration_minutes"]) == 15524.772
    assert episode["halt_close_status"] == "MULTI_DAY"

    t3_rows = source.fetch_core_episodes(
        ticker="GPUS",
        start_date=date(2026, 8, 14),
        end_date=date(2026, 8, 25),
        reason_codes=("T3",),
    )

    assert t3_rows == []
