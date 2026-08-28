from datetime import datetime, time
from decimal import Decimal
from typing import Any

from shared.database import get_connection


# ============================================================
# QuantLab - Nasdaq PostgreSQL Persistence
# VERSION 0.7
# ============================================================

VERSION = "0.7"

ALLOWED_HALT_CLOSE_STATUS = {
    "YES",
    "NO",
    "UNKNOWN",
    "MULTI_DAY",
}


# ============================================================
# OUTILS DE CONVERSION
# ============================================================

def empty_to_none(value: Any):
    """
    Convertit les chaînes vides en None.
    """

    if value is None:
        return None

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return None

    return value


def parse_date(value):
    """
    Convertit une date Nasdaq MM/DD/YYYY en date Python.
    """

    value = empty_to_none(value)

    if value is None:
        return None

    if hasattr(value, "year") and not isinstance(
        value,
        str
    ):
        return value

    return datetime.strptime(
        value,
        "%m/%d/%Y"
    ).date()


def parse_time(value):
    """
    Convertit une heure Nasdaq en time Python.

    Les données Nasdaq peuvent contenir des espaces avant
    les fractions de seconde, par exemple :

        08:52:20                      .892

    Les espaces sont retirés sans perdre la précision.
    """

    value = empty_to_none(value)

    if value is None:
        return None

    if isinstance(value, time):
        return value

    value = value.replace(
        " ",
        ""
    )

    return time.fromisoformat(
        value
    )


def parse_decimal(value):
    """
    Convertit une valeur numérique en Decimal.
    """

    value = empty_to_none(value)

    if value is None:
        return None

    return Decimal(
        str(value)
    )


def parse_halt_close_status(value):
    """
    Valide le statut d'un épisode à la clôture.
    """

    value = empty_to_none(value)

    if value is None:
        return None

    value = str(
        value
    ).upper()

    if value not in ALLOWED_HALT_CLOSE_STATUS:

        raise ValueError(
            "Unexpected halt_close_status value: "
            f"{value}"
        )

    return value


# ============================================================
# IDENTITÉ RAW
# ============================================================

def get_raw_natural_key(event):
    """
    Retourne la clé naturelle PostgreSQL d'un événement RAW.

    Cette clé correspond à la contrainte UNIQUE de :

        raw.nasdaq_trade_halt

    Clé :
        symbol
        halt_date
        halt_time
        reason_code
        market
    """

    halt_start = event.get(
        "halt_start"
    )

    if halt_start is None:

        raise ValueError(
            "RAW event has no halt_start: "
            f"{event}"
        )

    symbol = empty_to_none(
        event.get("symbol")
    )

    market = empty_to_none(
        event.get("market")
    )

    reason_code = empty_to_none(
        event.get("reason_code")
    )

    if symbol is None:

        raise ValueError(
            "RAW event has no symbol."
        )

    if market is None:

        raise ValueError(
            f"RAW event has no market: {symbol}"
        )

    if reason_code is None:

        raise ValueError(
            f"RAW event has no reason_code: {symbol}"
        )

    return (
        symbol,
        halt_start.date(),
        halt_start.time(),
        reason_code,
        market,
    )


# ============================================================
# CORRESPONDANCE EPISODE -> RAW
# ============================================================

def find_source_event_for_episode(
    episode,
    unique_events
):
    """
    Trouve l'événement RAW qui correspond à un épisode.

    Pour la V0.7, la relation doit être strictement 1:1.

    Un épisode doit correspondre exactement à un événement
    selon :

        symbol
        market
        reason_code
        halt_start
        halt_end

    Si aucun événement ou plusieurs événements correspondent,
    l'écriture est interrompue.

    Cette stratégie est volontairement stricte afin de détecter
    si le modèle 1 RAW -> 1 CORE cesse d'être valide sur
    l'historique complet.
    """

    candidates = []

    for event in unique_events:

        if (
            event.get("symbol")
            == episode.get("symbol")

            and

            event.get("market")
            == episode.get("market")

            and

            event.get("reason_code")
            == episode.get("reason_code")

            and

            event.get("halt_start")
            == episode.get("halt_start")

            and

            event.get("halt_end")
            == episode.get("halt_end")
        ):

            candidates.append(
                event
            )

    if len(candidates) == 0:

        raise RuntimeError(
            "No unique RAW event found for episode "
            f"{episode.get('episode_id')} "
            f"{episode.get('symbol')} "
            f"{episode.get('halt_start')}. "
            "The episode may represent multiple RAW events. "
            "The PostgreSQL CORE model must be reviewed "
            "before continuing."
        )

    if len(candidates) > 1:

        raise RuntimeError(
            "Multiple RAW events found for episode "
            f"{episode.get('episode_id')} "
            f"{episode.get('symbol')} "
            f"{episode.get('halt_start')}. "
            "The PostgreSQL CORE model cannot represent "
            "this relationship unambiguously."
        )

    return candidates[0]


# ============================================================
# ÉCRITURE RAW
# ============================================================

def write_trade_halts(
    conn,
    unique_events
):
    """
    Écrit les événements Nasdaq dans :

        raw.nasdaq_trade_halt

    Retourne :

        inserted
        existing
        raw_ids

    raw_ids associe chaque clé naturelle au ID PostgreSQL.
    """

    insert_sql = """
        INSERT INTO raw.nasdaq_trade_halt (
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
            source_file
        )
        VALUES (
            %(symbol)s,
            %(issue_name)s,
            %(market)s,
            %(reason_code)s,
            %(halt_date)s,
            %(halt_time)s,
            %(resumption_date)s,
            %(resumption_quote_time)s,
            %(resumption_trade_time)s,
            %(pause_threshold_price)s,
            %(source_file)s
        )
        ON CONFLICT (
            symbol,
            halt_date,
            halt_time,
            reason_code,
            market
        )
        DO NOTHING
        RETURNING id;
    """

    select_sql = """
        SELECT id
        FROM raw.nasdaq_trade_halt
        WHERE symbol = %(symbol)s
          AND halt_date = %(halt_date)s
          AND halt_time = %(halt_time)s
          AND reason_code = %(reason_code)s
          AND market = %(market)s;
    """

    inserted = 0
    existing = 0

    raw_ids = {}

    with conn.cursor() as cur:

        for event in unique_events:

            source_file = empty_to_none(
                event.get("source_file")
            )

            if source_file is None:

                raise ValueError(
                    "RAW event has no source_file: "
                    f"{event.get('symbol')} "
                    f"{event.get('halt_start')}"
                )

            halt_start = event.get(
                "halt_start"
            )

            if halt_start is None:

                raise ValueError(
                    "RAW event has no halt_start: "
                    f"{event.get('symbol')}"
                )

            params = {
                "symbol":
                    event["symbol"],

                "issue_name":
                    empty_to_none(
                        event.get(
                            "issue_name"
                        )
                    ),

                "market":
                    event["market"],

                "reason_code":
                    event["reason_code"],

                "halt_date":
                    halt_start.date(),

                "halt_time":
                    halt_start.time(),

                "resumption_date":
                    parse_date(
                        event.get(
                            "resumption_date"
                        )
                    ),

                "resumption_quote_time":
                    parse_time(
                        event.get(
                            "resumption_quote_time"
                        )
                    ),

                "resumption_trade_time":
                    parse_time(
                        event.get(
                            "resumption_trade_time"
                        )
                    ),

                "pause_threshold_price":
                    parse_decimal(
                        event.get(
                            "pause_threshold_price"
                        )
                    ),

                "source_file":
                    source_file,
            }

            cur.execute(
                insert_sql,
                params
            )

            result = cur.fetchone()

            if result is not None:

                raw_id = result[0]

                inserted += 1

            else:

                cur.execute(
                    select_sql,
                    params
                )

                existing_result = (
                    cur.fetchone()
                )

                if existing_result is None:

                    raise RuntimeError(
                        "RAW event conflict detected "
                        "but existing PostgreSQL row "
                        "could not be retrieved: "
                        f"{event.get('symbol')} "
                        f"{halt_start}"
                    )

                raw_id = (
                    existing_result[0]
                )

                existing += 1

            natural_key = (
                get_raw_natural_key(
                    event
                )
            )

            if natural_key in raw_ids:

                raise RuntimeError(
                    "Duplicate RAW natural key "
                    "detected in unique_events: "
                    f"{natural_key}"
                )

            raw_ids[
                natural_key
            ] = raw_id

    return (
        inserted,
        existing,
        raw_ids,
    )


# ============================================================
# ÉCRITURE CORE
# ============================================================

def write_halt_episodes(
    conn,
    episodes,
    unique_events,
    raw_ids
):
    """
    Écrit les épisodes Nasdaq dans :

        core.nasdaq_halt_episode

    Pour V0.7, un épisode doit être relié de façon
    non ambiguë à exactement un événement RAW.
    """

    insert_sql = """
        INSERT INTO core.nasdaq_halt_episode (
            trade_halt_id,
            collector_episode_id,
            symbol,
            issue_name,
            market,
            reason_code,
            halt_start,
            halt_end,
            duration_minutes,
            halt_close_status
        )
        VALUES (
            %(trade_halt_id)s,
            %(collector_episode_id)s,
            %(symbol)s,
            %(issue_name)s,
            %(market)s,
            %(reason_code)s,
            %(halt_start)s,
            %(halt_end)s,
            %(duration_minutes)s,
            %(halt_close_status)s
        )
        ON CONFLICT (
            trade_halt_id
        )
        DO NOTHING
        RETURNING id;
    """

    inserted = 0
    existing = 0

    with conn.cursor() as cur:

        for episode in episodes:

            source_event = (
                find_source_event_for_episode(
                    episode,
                    unique_events
                )
            )

            natural_key = (
                get_raw_natural_key(
                    source_event
                )
            )

            trade_halt_id = (
                raw_ids.get(
                    natural_key
                )
            )

            if trade_halt_id is None:

                raise RuntimeError(
                    "PostgreSQL RAW id not found "
                    "for episode "
                    f"{episode.get('episode_id')} "
                    f"{episode.get('symbol')}."
                )

            duration_minutes = (
                empty_to_none(
                    episode.get(
                        "duration_minutes"
                    )
                )
            )

            params = {
                "trade_halt_id":
                    trade_halt_id,

                "collector_episode_id":
                    empty_to_none(
                        episode.get(
                            "episode_id"
                        )
                    ),

                "symbol":
                    episode["symbol"],

                "issue_name":
                    empty_to_none(
                        episode.get(
                            "issue_name"
                        )
                    ),

                "market":
                    empty_to_none(
                        episode.get(
                            "market"
                        )
                    ),

                "reason_code":
                    empty_to_none(
                        episode.get(
                            "reason_code"
                        )
                    ),

                "halt_start":
                    episode["halt_start"],

                "halt_end":
                    episode.get(
                        "halt_end"
                    ),

                "duration_minutes":
                    duration_minutes,

                "halt_close_status":
                    parse_halt_close_status(
                        episode.get(
                            "halt_at_close"
                        )
                    ),
            }

            cur.execute(
                insert_sql,
                params
            )

            result = cur.fetchone()

            if result is None:

                existing += 1

            else:

                inserted += 1

    return (
        inserted,
        existing,
    )


# ============================================================
# PERSISTANCE COMPLÈTE
# ============================================================

def persist_nasdaq_halts(
    unique_events,
    episodes
):
    """
    Persiste une exécution Nasdaq complète dans PostgreSQL.

    La connexion est gérée dans une transaction unique :

        RAW
        puis
        CORE

    Toute erreur provoque le rollback de l'ensemble de
    l'opération.
    """

    print()
    print(
        "============================================================"
    )
    print(
        f"POSTGRESQL PERSISTENCE V{VERSION}"
    )
    print(
        "============================================================"
    )
    print()

    with get_connection() as conn:

        (
            raw_inserted,
            raw_existing,
            raw_ids,
        ) = write_trade_halts(
            conn,
            unique_events
        )

        (
            core_inserted,
            core_existing,
        ) = write_halt_episodes(
            conn,
            episodes,
            unique_events,
            raw_ids
        )

    print(
        f"RAW inserted          : {raw_inserted}"
    )

    print(
        f"RAW existing          : {raw_existing}"
    )

    print(
        f"CORE inserted         : {core_inserted}"
    )

    print(
        f"CORE existing         : {core_existing}"
    )

    print()

    print(
        "PostgreSQL persistence completed ✓"
    )

    return {
        "raw_inserted":
            raw_inserted,

        "raw_existing":
            raw_existing,

        "core_inserted":
            core_inserted,

        "core_existing":
            core_existing,
    }
