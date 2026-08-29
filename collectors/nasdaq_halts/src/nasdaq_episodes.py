from collections import defaultdict
from datetime import time


# ============================================================
# QUANTLAB - NASDAQ HALT EPISODES
# VERSION 0.9
# ============================================================

VERSION = "0.9"

MARKET_CLOSE = time(
    16,
    0,
    0
)


# ============================================================
# NORMALISATION DES MARCHÉS
# ============================================================

MARKET_ALIASES = {
    "Q": "NASDAQ",
    "NASDAQ": "NASDAQ",
    "N": "NYSE",
    "NYSE": "NYSE",
    "A": "AMEX",
    "AMEX": "AMEX",
}


def normalize_market(market):
    """
    Normalise les alias de marché connus.

    Les valeurs RAW originales ne sont jamais modifiées.

    Alias connus :

        Q      -> NASDAQ
        NASDAQ -> NASDAQ
        N      -> NYSE
        NYSE   -> NYSE
        A      -> AMEX
        AMEX   -> AMEX

    Les autres marchés sont conservés tels quels.
    """

    if market is None:
        return None

    return MARKET_ALIASES.get(
        market,
        market
    )


# ============================================================
# CONSTRUCTION DES ÉPISODES
# ============================================================

def build_halt_episodes(
    unique_events,
    market_close=MARKET_CLOSE
):
    """
    Construit les épisodes HALT à partir des événements
    Nasdaq normalisés.

    VERSION 0.9 :

    Les événements sont regroupés selon :

        symbol
        market normalisé
        reason_code

    Les alias de marché connus sont donc regroupés :

        Q / NASDAQ -> NASDAQ
        N / NYSE   -> NYSE
        A / AMEX   -> AMEX

    Les autres marchés restent distincts.

    Deux événements appartenant au même groupe font partie
    du même épisode si :

    - leur halt_start est identique;
    - ou leur halt_start chevauche l'épisode courant.

    Retourne :

        episodes
        statistics
    """

    events_by_group = defaultdict(
        list
    )

    for event in unique_events:

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


    # ========================================================
    # CONSTRUCTION DES ÉPISODES
    # ========================================================

    episodes = []

    for (
        symbol,
        market,
        reason_code,
    ), events in events_by_group.items():

        events.sort(
            key=lambda x: x["halt_start"]
        )

        current = None

        for event in events:

            start = event[
                "halt_start"
            ]

            end = event[
                "halt_end"
            ]

            # ------------------------------------------------
            # Premier événement
            # ------------------------------------------------

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

                    "pause_threshold_price":
                        event[
                            "pause_threshold_price"
                        ],
                }

                continue

            current_start = current[
                "halt_start"
            ]

            current_end = current[
                "halt_end"
            ]

            # ------------------------------------------------
            # Même épisode :
            #
            # - même début
            # - ou chevauchement
            # ------------------------------------------------

            same_episode = False

            if start == current_start:

                same_episode = True

            elif (
                current_end is not None
                and start <= current_end
            ):

                same_episode = True

            if same_episode:

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

                episodes.append(
                    current
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

                    "pause_threshold_price":
                        event[
                            "pause_threshold_price"
                        ],
                }

        if current is not None:

            episodes.append(
                current
            )


    # ========================================================
    # IDENTIFIANT D'ÉPISODE
    # ========================================================

    for index, episode in enumerate(
        episodes,
        start=1
    ):

        episode[
            "episode_id"
        ] = f"H{index:08d}"


    # ========================================================
    # CALCUL DES DURÉES
    # ========================================================

    duration_count = 0

    for episode in episodes:

        start = episode[
            "halt_start"
        ]

        end = episode[
            "halt_end"
        ]

        if (
            start is not None
            and end is not None
            and end >= start
        ):

            duration = (
                end - start
            ).total_seconds() / 60.0

            episode[
                "duration_minutes"
            ] = round(
                duration,
                3
            )

            duration_count += 1

        else:

            episode[
                "duration_minutes"
            ] = ""


    # ========================================================
    # STATUT HALT À LA CLÔTURE
    # ========================================================

    close_yes = 0
    close_no = 0
    close_unknown = 0
    close_multi_day = 0

    for episode in episodes:

        start = episode[
            "halt_start"
        ]

        end = episode[
            "halt_end"
        ]

        if (
            start is None
            or end is None
        ):

            episode[
                "halt_at_close"
            ] = "UNKNOWN"

            close_unknown += 1

            continue

        # ----------------------------------------------------
        # Même journée
        # ----------------------------------------------------

        if start.date() == end.date():

            if (
                start.time()
                <= market_close
                <= end.time()
            ):

                episode[
                    "halt_at_close"
                ] = "YES"

                close_yes += 1

            else:

                episode[
                    "halt_at_close"
                ] = "NO"

                close_no += 1

        else:

            # ------------------------------------------------
            # Episode multi-day.
            #
            # Le statut de clôture détaillé est calculé
            # au niveau DAILY.
            # ------------------------------------------------

            episode[
                "halt_at_close"
            ] = "MULTI_DAY"

            close_multi_day += 1


    # ========================================================
    # STATISTIQUES
    # ========================================================

    statistics = {
        "episode_count":
            len(episodes),

        "duration_count":
            duration_count,

        "close_yes":
            close_yes,

        "close_no":
            close_no,

        "close_unknown":
            close_unknown,

        "close_multi_day":
            close_multi_day,
    }

    return (
        episodes,
        statistics
    )
