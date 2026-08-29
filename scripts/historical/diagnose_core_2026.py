from collections import defaultdict
from datetime import datetime

from collectors.nasdaq_halts.src.nasdaq_episodes import (
    build_halt_episodes,
    normalize_market,
)
from shared.database import get_connection


START_DATE = "2026-01-01"
END_DATE = "2026-09-01"


def load_raw_events():
    """
    Lit les événements RAW 2026 depuis PostgreSQL.

    Aucune écriture dans la base.
    """

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                """
                SELECT
                    id,
                    symbol,
                    issue_name,
                    market,
                    reason_code,
                    halt_date,
                    halt_time,
                    resumption_date,
                    resumption_quote_time,
                    resumption_trade_time,
                    pause_threshold_price
                FROM raw.nasdaq_trade_halt
                WHERE halt_date >= %s
                  AND halt_date < %s
                ORDER BY symbol, halt_date, halt_time, id
                """,
                (
                    START_DATE,
                    END_DATE,
                ),
            )

            rows = cur.fetchall()

    events = []

    for row in rows:

        (
            raw_id,
            symbol,
            issue_name,
            market,
            reason_code,
            halt_date,
            halt_time,
            resumption_date,
            resumption_quote_time,
            resumption_trade_time,
            pause_threshold_price,
        ) = row

        halt_start = datetime.combine(
            halt_date,
            halt_time,
        )

        halt_end = None

        resumption_time = (
            resumption_trade_time
            or resumption_quote_time
        )

        if (
            resumption_date is not None
            and resumption_time is not None
        ):

            halt_end = datetime.combine(
                resumption_date,
                resumption_time,
            )

        events.append(
            {
                "raw_id": raw_id,
                "symbol": symbol,
                "issue_name": issue_name,
                "market": market,
                "reason_code": reason_code,
                "halt_date": halt_date,
                "halt_time": halt_time,
                "resumption_date": resumption_date,
                "resumption_quote_time":
                    resumption_quote_time,
                "resumption_trade_time":
                    resumption_trade_time,
                "pause_threshold_price":
                    pause_threshold_price,
                "halt_start": halt_start,
                "halt_end": halt_end,
            }
        )

    return events


def analyze_groups(events):
    """
    Analyse les groupes RAW selon exactement les mêmes
    dimensions utilisées par build_halt_episodes() V0.9 :

        symbol
        market normalisé
        reason_code

    Cette fonction ne modifie aucune donnée.

    Elle conserve les RAW events appartenant à chaque
    groupe afin de permettre le diagnostic des relations
    RAW -> CORE.
    """

    events_by_group = defaultdict(list)

    for event in events:

        if event["halt_start"] is not None:

            market = normalize_market(
                event["market"]
            )

            key = (
                event["symbol"],
                market,
                event["reason_code"],
            )

            events_by_group[
                key
            ].append(
                event
            )

    groups = []

    for (
        symbol,
        market,
        reason_code,
    ), group_events in events_by_group.items():

        group_events.sort(
            key=lambda x: x["halt_start"]
        )

        current = None
        current_events = []

        for event in group_events:

            start = event["halt_start"]
            end = event["halt_end"]

            if current is None:

                current = {
                    "symbol":
                        symbol,

                    "issue_name":
                        event["issue_name"],

                    "market":
                        market,

                    "reason_code":
                        reason_code,

                    "halt_start":
                        start,

                    "halt_end":
                        end,
                }

                current_events = [
                    event
                ]

                continue

            current_start = current[
                "halt_start"
            ]

            current_end = current[
                "halt_end"
            ]

            same_episode = False

            if start == current_start:

                same_episode = True

            elif (
                current_end is not None
                and start <= current_end
            ):

                same_episode = True

            if same_episode:

                current_events.append(
                    event
                )

                if start < current_start:

                    current[
                        "halt_start"
                    ] = start

                if end is not None:

                    if (
                        current_end is None
                        or end > current_end
                    ):

                        current[
                            "halt_end"
                        ] = end

            else:

                groups.append(
                    (
                        current.copy(),
                        list(current_events),
                    )
                )

                current = {
                    "symbol":
                        symbol,

                    "issue_name":
                        event["issue_name"],

                    "market":
                        market,

                    "reason_code":
                        reason_code,

                    "halt_start":
                        start,

                    "halt_end":
                        end,
                }

                current_events = [
                    event
                ]

        if current is not None:

            groups.append(
                (
                    current.copy(),
                    list(current_events),
                )
            )

    return groups


def main():

    print()
    print("=" * 60)
    print("QUANTLAB - CORE 2026 DIAGNOSTIC")
    print("=" * 60)
    print()

    print(
        f"Période RAW : {START_DATE} → "
        f"{END_DATE}"
    )
    print()

    events = load_raw_events()

    print(
        f"RAW events                  : "
        f"{len(events)}"
    )

    # --------------------------------------------------------
    # Build officiel
    # --------------------------------------------------------

    episodes, statistics = build_halt_episodes(
        events
    )

    print(
        f"Episodes build_halt_episodes : "
        f"{len(episodes)}"
    )

    print(
        f"Durées calculables          : "
        f"{statistics['duration_count']}"
    )

    print(
        f"HALT close YES              : "
        f"{statistics['close_yes']}"
    )

    print(
        f"HALT close NO               : "
        f"{statistics['close_no']}"
    )

    print(
        f"HALT UNKNOWN                : "
        f"{statistics['close_unknown']}"
    )

    print(
        f"HALT MULTI_DAY              : "
        f"{statistics['close_multi_day']}"
    )

    print()

    # --------------------------------------------------------
    # Analyse des groupes RAW
    # --------------------------------------------------------

    groups = analyze_groups(
        events
    )

    if len(groups) != len(episodes):

        raise RuntimeError(
            "Diagnostic grouping mismatch: "
            f"{len(groups)} groups vs "
            f"{len(episodes)} episodes."
        )

    group_sizes = [
        len(raw_events)
        for _, raw_events in groups
    ]

    merged_groups = [
        (episode, raw_events)
        for episode, raw_events in groups
        if len(raw_events) > 1
    ]

    one_to_one_groups = [
        (episode, raw_events)
        for episode, raw_events in groups
        if len(raw_events) == 1
    ]

    # --------------------------------------------------------
    # Groupes multi-market
    # --------------------------------------------------------

    multi_market = []

    for episode, raw_events in merged_groups:

        markets = {
            normalize_market(
                event["market"]
            )
            for event in raw_events
        }

        if len(markets) > 1:

            multi_market.append(
                (
                    episode,
                    raw_events,
                    markets,
                )
            )

    # --------------------------------------------------------
    # Groupes multi-reason
    # --------------------------------------------------------

    multi_reason = []

    for episode, raw_events in merged_groups:

        reasons = {
            event["reason_code"]
            for event in raw_events
        }

        if len(reasons) > 1:

            multi_reason.append(
                (
                    episode,
                    raw_events,
                    reasons,
                )
            )

    print("=" * 60)
    print("GROUPING DIAGNOSTIC")
    print("=" * 60)
    print()

    print(
        f"Total groups                : "
        f"{len(groups)}"
    )

    print(
        f"1 RAW → 1 CORE              : "
        f"{len(one_to_one_groups)}"
    )

    print(
        f"Multi-RAW → 1 CORE          : "
        f"{len(merged_groups)}"
    )

    print(
        f"Multi-market groups         : "
        f"{len(multi_market)}"
    )

    print(
        f"Multi-reason groups         : "
        f"{len(multi_reason)}"
    )

    print()

    if group_sizes:

        print(
            f"Maximum RAW events/group    : "
            f"{max(group_sizes)}"
        )

    print()

    # --------------------------------------------------------
    # Affichage des groupes fusionnés
    # --------------------------------------------------------

    if merged_groups:

        print("=" * 60)
        print("MERGED GROUPS")
        print("=" * 60)
        print()

        for index, (
            episode,
            raw_events,
        ) in enumerate(
            merged_groups,
            start=1,
        ):

            raw_markets = {
                event["market"]
                for event in raw_events
            }

            normalized_markets = {
                normalize_market(
                    event["market"]
                )
                for event in raw_events
            }

            reasons = {
                event["reason_code"]
                for event in raw_events
            }

            if (
                len(normalized_markets) == 1
                and len(reasons) == 1
                and len(raw_markets) > 1
            ):

                classification = (
                    "MARKET_ALIAS_COLLAPSE"
                )

            elif (
                len(normalized_markets) == 1
                and len(reasons) == 1
            ):

                classification = (
                    "SAME_MARKET_SAME_REASON"
                )

            elif (
                len(normalized_markets) > 1
                and len(reasons) == 1
            ):

                classification = (
                    "DIFFERENT_MARKET_SAME_REASON"
                )

            elif (
                len(normalized_markets) == 1
                and len(reasons) > 1
            ):

                classification = (
                    "SAME_MARKET_DIFFERENT_REASON"
                )

            else:

                classification = (
                    "DIFFERENT_MARKET_DIFFERENT_REASON"
                )

            print(
                f"[{index}] "
                f"{episode['symbol']} "
                f"{episode['halt_start']} → "
                f"{episode['halt_end']}"
            )

            print(
                f"     Classification : "
                f"{classification}"
            )

            print(
                f"     RAW markets    : "
                f"{sorted(raw_markets)}"
            )

            print(
                f"     CORE market    : "
                f"{episode['market']}"
            )

            print(
                f"     Reasons        : "
                f"{sorted(reasons)}"
            )

            print(
                f"     RAW events     : "
                f"{len(raw_events)}"
            )

            for event in raw_events:

                print(
                    f"       id={event['raw_id']} "
                    f"{event['symbol']} "
                    f"{event['market']} "
                    f"{event['reason_code']} "
                    f"{event['halt_start']} → "
                    f"{event['halt_end']}"
                )

            print()

    # --------------------------------------------------------
    # Vérifications finales
    # --------------------------------------------------------

    if len(events) != (
        len(one_to_one_groups)
        + sum(
            len(raw_events)
            for _, raw_events in merged_groups
        )
    ):

        raise RuntimeError(
            "Diagnostic RAW grouping count mismatch."
        )

    print("=" * 60)
    print("CORE 2026 DIAGNOSTIC : PASS")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
