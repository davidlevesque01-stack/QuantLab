from collections import defaultdict
from datetime import time

VERSION = "1.2"

MARKET_CLOSE = time(16, 0, 0)

MARKET_ALIASES = {
    "Q": "NASDAQ",
    "NASDAQ": "NASDAQ",
    "N": "NYSE",
    "NYSE": "NYSE",
    "A": "AMEX",
    "AMEX": "AMEX",
}


def normalize_market(market):
    """Normalize known market aliases without changing RAW."""
    if market is None:
        return None
    market = str(market).upper()
    return MARKET_ALIASES.get(market, market)


def build_halt_episodes(unique_events, market_close=MARKET_CLOSE):
    """
    Build CORE HALT episodes.

    V1.2 business rule:
    - CORE identity is symbol + normalized market + continuous HALT period.
    - reason_code never creates a separate CORE episode.
    - a halt_start opens a HALT.
    - the HALT remains open until a valid halt_end is observed.
    - NULL or invalid halt_end (< halt_start) never closes a HALT.
    - while the current HALT has no valid end, every later event for the
      same symbol/market belongs to that same open episode.
    - once a valid end exists, an event starting after that end opens a new
      episode.
    - multiple reason codes in the same HALT are retained in reason_codes.
    - RAW events are never modified.

    Examples:
        ABC 12:45:56 -> NULL
        ABC 12:45:56 -> 13:23:12
        => one CORE episode, ending 13:23:12

        ABC 12:45:56 -> NULL
        ABC 12:50:00 -> NULL
        ABC 13:23:12 -> 13:30:00
        => one CORE episode, ending 13:30:00

        ABC 12:45:56 -> 13:23:12
        ABC 13:30:00 -> 13:40:00
        => two CORE episodes
    """
    events_by_group = defaultdict(list)
    invalid_end_count = 0

    for event in unique_events:
        start = event.get("halt_start")
        if start is None:
            continue

        market = normalize_market(event.get("market"))
        raw_end = event.get("halt_end")

        if raw_end is not None and raw_end < start:
            invalid_end_count += 1

        events_by_group[(event.get("symbol"), market)].append(event)

    episodes = []

    for (symbol, market), events in events_by_group.items():
        events.sort(
            key=lambda x: (
                x["halt_start"],
                x.get("halt_end")
                if (
                    x.get("halt_end") is not None
                    and x.get("halt_end") >= x["halt_start"]
                )
                else x["halt_start"],
            )
        )

        current = None
        current_reason_codes = set()

        for event in events:
            start = event["halt_start"]
            raw_end = event.get("halt_end")
            end = (
                raw_end
                if raw_end is not None and raw_end >= start
                else None
            )

            if current is None:
                reason_code = event.get("reason_code")
                current_reason_codes = set()
                if reason_code is not None:
                    current_reason_codes.add(reason_code)

                current = {
                    "symbol": symbol,
                    "issue_name": event.get("issue_name"),
                    "market": market,
                    "reason_code": reason_code,
                    "reason_codes": current_reason_codes,
                    "halt_start": start,
                    "halt_end": end,
                    "pause_threshold_price": event.get(
                        "pause_threshold_price"
                    ),
                }
                continue

            current_start = current["halt_start"]
            current_end = current["halt_end"]

            # Core business rule:
            # an open HALT remains open until a valid end is known.
            if current_end is None:
                same_episode = True
            else:
                same_episode = start <= current_end

            if same_episode:
                if start < current_start:
                    current["halt_start"] = start

                if end is not None and (
                    current_end is None or end > current_end
                ):
                    current["halt_end"] = end

                reason_code = event.get("reason_code")
                if reason_code is not None:
                    current_reason_codes.add(reason_code)

                if (
                    current.get("issue_name") is None
                    and event.get("issue_name") is not None
                ):
                    current["issue_name"] = event.get("issue_name")

                if (
                    current.get("pause_threshold_price") is None
                    and event.get("pause_threshold_price") is not None
                ):
                    current["pause_threshold_price"] = event.get(
                        "pause_threshold_price"
                    )

            else:
                current["reason_code"] = (
                    next(iter(current_reason_codes))
                    if len(current_reason_codes) == 1
                    else None
                )
                episodes.append(current)

                reason_code = event.get("reason_code")
                current_reason_codes = set()
                if reason_code is not None:
                    current_reason_codes.add(reason_code)

                current = {
                    "symbol": symbol,
                    "issue_name": event.get("issue_name"),
                    "market": market,
                    "reason_code": reason_code,
                    "reason_codes": current_reason_codes,
                    "halt_start": start,
                    "halt_end": end,
                    "pause_threshold_price": event.get(
                        "pause_threshold_price"
                    ),
                }

        if current is not None:
            current["reason_code"] = (
                next(iter(current_reason_codes))
                if len(current_reason_codes) == 1
                else None
            )
            episodes.append(current)

    for episode in episodes:
        episode["reason_codes"] = sorted(
            episode.get("reason_codes", set())
        )

    for index, episode in enumerate(episodes, start=1):
        episode["episode_id"] = f"H{index:08d}"

    duration_count = 0

    for episode in episodes:
        start = episode["halt_start"]
        end = episode["halt_end"]

        if start is not None and end is not None and end >= start:
            episode["duration_minutes"] = round(
                (end - start).total_seconds() / 60.0,
                3,
            )
            duration_count += 1
        else:
            episode["duration_minutes"] = None

    close_yes = 0
    close_no = 0
    close_unknown = 0
    close_multi_day = 0

    for episode in episodes:
        start = episode["halt_start"]
        end = episode["halt_end"]

        if start is None or end is None:
            episode["halt_at_close"] = "UNKNOWN"
            close_unknown += 1
            continue

        if start.date() == end.date():
            if start.time() <= market_close <= end.time():
                episode["halt_at_close"] = "YES"
                close_yes += 1
            else:
                episode["halt_at_close"] = "NO"
                close_no += 1
        else:
            episode["halt_at_close"] = "MULTI_DAY"
            close_multi_day += 1

    multi_reason_count = sum(
        1 for episode in episodes
        if len(episode.get("reason_codes", [])) > 1
    )

    statistics = {
        "episode_count": len(episodes),
        "duration_count": duration_count,
        "close_yes": close_yes,
        "close_no": close_no,
        "close_unknown": close_unknown,
        "close_multi_day": close_multi_day,
        "invalid_end_count": invalid_end_count,
        "multi_reason_count": multi_reason_count,
    }

    return episodes, statistics
