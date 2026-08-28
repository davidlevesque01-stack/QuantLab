from datetime import datetime, time
from decimal import Decimal
from typing import Any

from shared.database import get_connection


# ============================================================
# QuantLab - Nasdaq PostgreSQL Persistence
# VERSION 0.8
# ============================================================

VERSION = "0.8"

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


def prefer_new_value(
    existing_value,
    incoming_value
):
    """
    Retourne la valeur à conserver.

    Règles V0.8 :

        NULL -> NULL       : conserve NULL
        NULL -> valeur     : prend la nouvelle valeur
        valeur -> NULL     : conserve la valeur existante
        valeur A -> A      : conserve A
        valeur A -> B      : prend B

    Une observation Nasdaq vide ne peut donc jamais effacer
    une information déjà connue.
    """

    if incoming_value is None:
        return existing_value

    return incoming_value


def prefer_close_status(
    existing_status,
    incoming_status
):
    """
    Retourne le statut de clôture à conserver.

    UNKNOWN est considéré comme moins informatif qu'un statut
    final déjà connu.

    Ainsi :

        YES/MULTI_DAY/NO -> UNKNOWN

    ne provoque pas de régression.

    Un nouveau statut final peut toutefois corriger un statut
    final précédent si les nouvelles données Nasdaq le justifient.
    """

    if incoming_status is None:
        return existing_status

    if (
        incoming_status == "UNKNOWN"
        and
        existing_status in {
            "YES",
            "NO",
            "MULTI_DAY",
        }
    ):
        return existing_status

    return incoming_status


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

    Pour la V0.8, la relation demeure strictement 1:1.

    Un épisode doit correspondre exactement à un événement
    selon :

        symbol
        market
        reason_code
        halt_start
        halt_end

    Si aucun événement ou plusieurs événements correspondent,
    l'écriture est interrompue.

    Cette stratégie demeure volontairement stricte afin de
    détecter si le modèle 1 RAW -> 1 CORE cesse d'être valide.
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

    La V0.8 distingue :

        inserted
        updated
        unchanged

    Les valeurs NULL entrantes n'effacent jamais une valeur
    existante.

    source_file représente le premier snapshot ayant créé
    l'événement RAW et n'est donc pas modifié lors d'un UPDATE.

    Retourne :

        inserted
        updated
        unchanged
        raw_ids
    """

    select_sql = """
        SELECT
            id,
            issue_name,
            resumption_date,
            resumption_quote_time,
            resumption_trade_time,
            pause_threshold_price,
            source_file
        FROM raw.nasdaq_trade_halt
        WHERE symbol = %(symbol)s
          AND halt_date = %(halt_date)s
          AND halt_time = %(halt_time)s
          AND reason_code = %(reason_code)s
          AND market = %(market)s;
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
        RETURNING id;
    """

    update_sql = """
        UPDATE raw.nasdaq_trade_halt
        SET
            issue_name = %(issue_name)s,
            resumption_date = %(resumption_date)s,
            resumption_quote_time = %(resumption_quote_time)s,
            resumption_trade_time = %(resumption_trade_time)s,
            pause_threshold_price = %(pause_threshold_price)s
        WHERE id = %(id)s;
    """

    inserted = 0
    updated = 0
    unchanged = 0

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
                select_sql,
                params
            )

            existing_row = (
                cur.fetchone()
            )

            if existing_row is None:

                cur.execute(
                    insert_sql,
                    params
                )

                result = cur.fetchone()

                if result is None:

                    raise RuntimeError(
                        "RAW INSERT did not return an id: "
                        f"{event.get('symbol')} "
                        f"{halt_start}"
                    )

                raw_id = result[0]

                inserted += 1

            else:

                (
                    raw_id,
                    existing_issue_name,
                    existing_resumption_date,
                    existing_resumption_quote_time,
                    existing_resumption_trade_time,
                    existing_pause_threshold_price,
                    existing_source_file,
                ) = existing_row

                desired_issue_name = (
                    prefer_new_value(
                        existing_issue_name,
                        params["issue_name"]
                    )
                )

                desired_resumption_date = (
                    prefer_new_value(
                        existing_resumption_date,
                        params["resumption_date"]
                    )
                )

                desired_resumption_quote_time = (
                    prefer_new_value(
                        existing_resumption_quote_time,
                        params[
                            "resumption_quote_time"
                        ]
                    )
                )

                desired_resumption_trade_time = (
                    prefer_new_value(
                        existing_resumption_trade_time,
                        params[
                            "resumption_trade_time"
                        ]
                    )
                )

                desired_pause_threshold_price = (
                    prefer_new_value(
                        existing_pause_threshold_price,
                        params[
                            "pause_threshold_price"
                        ]
                    )
                )

                has_changes = any(
                    (
                        desired_issue_name
                        != existing_issue_name,

                        desired_resumption_date
                        != existing_resumption_date,

                        desired_resumption_quote_time
                        != existing_resumption_quote_time,

                        desired_resumption_trade_time
                        != existing_resumption_trade_time,

                        desired_pause_threshold_price
                        != existing_pause_threshold_price,
                    )
                )

                if has_changes:

                    update_params = {
                        "id":
                            raw_id,

                        "issue_name":
                            desired_issue_name,

                        "resumption_date":
                            desired_resumption_date,

                        "resumption_quote_time":
                            desired_resumption_quote_time,

                        "resumption_trade_time":
                            desired_resumption_trade_time,

                        "pause_threshold_price":
                            desired_pause_threshold_price,
                    }

                    cur.execute(
                        update_sql,
                        update_params
                    )

                    if cur.rowcount != 1:

                        raise RuntimeError(
                            "Unexpected RAW UPDATE row count "
                            f"for id {raw_id}: "
                            f"{cur.rowcount}"
                        )

                    updated += 1

                else:

                    unchanged += 1

                # V0.8 :
                # existing_source_file est volontairement conservé.
                # Un futur modèle de provenance permettra de relier
                # plusieurs snapshots au même événement RAW.
                _ = existing_source_file

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
        updated,
        unchanged,
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

    La V0.8 distingue :

        inserted
        updated
        unchanged

    Une valeur NULL entrante ne remplace jamais une valeur
    déjà connue.

    collector_episode_id est conservé après le premier INSERT,
    car les identifiants séquentiels produits actuellement par
    le calculateur ne constituent pas une identité persistante.

    UNKNOWN ne remplace pas un statut final déjà connu.
    """

    select_sql = """
        SELECT
            id,
            collector_episode_id,
            symbol,
            issue_name,
            market,
            reason_code,
            halt_start,
            halt_end,
            duration_minutes,
            halt_close_status
        FROM core.nasdaq_halt_episode
        WHERE trade_halt_id = %(trade_halt_id)s;
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
        RETURNING id;
    """

    update_sql = """
        UPDATE core.nasdaq_halt_episode
        SET
            issue_name = %(issue_name)s,
            market = %(market)s,
            reason_code = %(reason_code)s,
            halt_end = %(halt_end)s,
            duration_minutes = %(duration_minutes)s,
            halt_close_status = %(halt_close_status)s
        WHERE id = %(id)s;
    """

    inserted = 0
    updated = 0
    unchanged = 0

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
                parse_decimal(
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
                select_sql,
                params
            )

            existing_row = (
                cur.fetchone()
            )

            if existing_row is None:

                cur.execute(
                    insert_sql,
                    params
                )

                result = cur.fetchone()

                if result is None:

                    raise RuntimeError(
                        "CORE INSERT did not return an id "
                        "for trade_halt_id "
                        f"{trade_halt_id}"
                    )

                inserted += 1

            else:

                (
                    core_id,
                    existing_collector_episode_id,
                    existing_symbol,
                    existing_issue_name,
                    existing_market,
                    existing_reason_code,
                    existing_halt_start,
                    existing_halt_end,
                    existing_duration_minutes,
                    existing_halt_close_status,
                ) = existing_row

                if (
                    existing_symbol
                    != params["symbol"]
                ):

                    raise RuntimeError(
                        "CORE symbol mismatch for "
                        f"trade_halt_id {trade_halt_id}: "
                        f"{existing_symbol} != "
                        f"{params['symbol']}"
                    )

                if (
                    existing_halt_start
                    != params["halt_start"]
                ):

                    raise RuntimeError(
                        "CORE halt_start mismatch for "
                        f"trade_halt_id {trade_halt_id}: "
                        f"{existing_halt_start} != "
                        f"{params['halt_start']}"
                    )

                desired_issue_name = (
                    prefer_new_value(
                        existing_issue_name,
                        params["issue_name"]
                    )
                )

                desired_market = (
                    prefer_new_value(
                        existing_market,
                        params["market"]
                    )
                )

                desired_reason_code = (
                    prefer_new_value(
                        existing_reason_code,
                        params["reason_code"]
                    )
                )

                desired_halt_end = (
                    prefer_new_value(
                        existing_halt_end,
                        params["halt_end"]
                    )
                )

                desired_duration_minutes = (
                    prefer_new_value(
                        existing_duration_minutes,
                        params["duration_minutes"]
                    )
                )

                desired_halt_close_status = (
                    prefer_close_status(
                        existing_halt_close_status,
                        params["halt_close_status"]
                    )
                )

                has_changes = any(
                    (
                        desired_issue_name
                        != existing_issue_name,

                        desired_market
                        != existing_market,

                        desired_reason_code
                        != existing_reason_code,

                        desired_halt_end
                        != existing_halt_end,

                        desired_duration_minutes
                        != existing_duration_minutes,

                        desired_halt_close_status
                        != existing_halt_close_status,
                    )
                )

                if has_changes:

                    update_params = {
                        "id":
                            core_id,

                        "issue_name":
                            desired_issue_name,

                        "market":
                            desired_market,

                        "reason_code":
                            desired_reason_code,

                        "halt_end":
                            desired_halt_end,

                        "duration_minutes":
                            desired_duration_minutes,

                        "halt_close_status":
                            desired_halt_close_status,
                    }

                    cur.execute(
                        update_sql,
                        update_params
                    )

                    if cur.rowcount != 1:

                        raise RuntimeError(
                            "Unexpected CORE UPDATE row count "
                            f"for id {core_id}: "
                            f"{cur.rowcount}"
                        )

                    updated += 1

                else:

                    unchanged += 1

                # L'identifiant séquentiel du calculateur est
                # volontairement conservé tel qu'il a été créé.
                _ = existing_collector_episode_id

    return (
        inserted,
        updated,
        unchanged,
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

    La V0.8 distingue pour RAW et CORE :

        inserted
        updated
        unchanged
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
            raw_updated,
            raw_unchanged,
            raw_ids,
        ) = write_trade_halts(
            conn,
            unique_events
        )

        (
            core_inserted,
            core_updated,
            core_unchanged,
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
        f"RAW updated           : {raw_updated}"
    )

    print(
        f"RAW unchanged         : {raw_unchanged}"
    )

    print(
        f"CORE inserted         : {core_inserted}"
    )

    print(
        f"CORE updated          : {core_updated}"
    )

    print(
        f"CORE unchanged        : {core_unchanged}"
    )

    print()

    print(
        "PostgreSQL persistence completed ✓"
    )

    return {
        "raw_inserted":
            raw_inserted,

        "raw_updated":
            raw_updated,

        "raw_unchanged":
            raw_unchanged,

        "core_inserted":
            core_inserted,

        "core_updated":
            core_updated,

        "core_unchanged":
            core_unchanged,
    }
