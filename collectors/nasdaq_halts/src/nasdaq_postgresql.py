from datetime import datetime, time
from decimal import Decimal
from typing import Any

from shared.database import get_connection


# ============================================================
# QuantLab - Nasdaq PostgreSQL Persistence
# VERSION 1.1
# ============================================================

VERSION = "1.2"

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

    Clé V1.1 :
        symbol
        halt_date
        halt_time
        reason_code
        market
        resumption_date
        resumption_trade_time
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

    resumption_date = parse_date(
        event.get("resumption_date")
    )

    resumption_trade_time = parse_time(
        event.get("resumption_trade_time")
    )

    return (
        symbol,
        halt_start.date(),
        halt_start.time(),
        reason_code,
        market,
        resumption_date,
        resumption_trade_time,
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
# CORRESPONDANCE EPISODE -> RAW
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
    Normalise les codes de marché Nasdaq utilisés par les flux RAW.

    Les alias connus sont regroupés ainsi :

        Q / NASDAQ -> NASDAQ
        N / NYSE   -> NYSE
        A / AMEX   -> AMEX

    Les autres codes sont conservés tels quels.
    """

    market = empty_to_none(market)

    if market is None:
        return None

    return MARKET_ALIASES.get(
        str(market).upper(),
        str(market).upper(),
    )


def _build_episode_event_groups(unique_events):
    """
    Reconstruit les groupes RAW exactement selon la logique de
    build_halt_episodes() V1.2.

    Identité CORE :
        symbol + market normalisé + période HALT continue.

    Le reason_code ne sépare jamais les épisodes.

    Un HALT ouvert reste ouvert jusqu'à l'observation d'une
    halt_end valide. NULL et les fins antérieures au halt_start
    ne ferment donc jamais l'épisode.
    """

    from collections import defaultdict

    events_by_group = defaultdict(list)

    for event in unique_events:

        if event.get("halt_start") is None:
            continue

        key = (
            event["symbol"],
            normalize_market(event.get("market")),
        )

        events_by_group[key].append(event)

    groups = []

    for _, events in events_by_group.items():

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

        current_events = []
        current_start = None
        current_end = None

        for event in events:

            start = event["halt_start"]
            raw_end = event.get("halt_end")

            end = (
                raw_end
                if (
                    raw_end is not None
                    and raw_end >= start
                )
                else None
            )

            if not current_events:
                current_events = [event]
                current_start = start
                current_end = end
                continue

            if current_end is None:
                same_episode = True
            else:
                same_episode = start <= current_end

            if same_episode:

                current_events.append(event)

                if start < current_start:
                    current_start = start

                if end is not None and (
                    current_end is None
                    or end > current_end
                ):
                    current_end = end

            else:

                groups.append(current_events)

                current_events = [event]
                current_start = start
                current_end = end

        if current_events:
            groups.append(current_events)

    return groups


def _prepare_episode_raw_groups(
    episodes,
    unique_events,
    raw_ids,
):
    """
    Associe chaque épisode CORE aux événements RAW qui le composent.

    La correspondance est reconstruite à partir de la même logique
    de regroupement que build_halt_episodes().

    Retourne une liste de dictionnaires :

        {
            "episode": episode,
            "events": [...],
            "raw_ids": [...],
            "market": ...,
            "reason_code": ...,
            "issue_name": ...
        }
    """

    groups = _build_episode_event_groups(
        unique_events
    )

    if len(groups) != len(episodes):

        raise RuntimeError(
            "Episode grouping mismatch: "
            f"{len(groups)} RAW groups vs "
            f"{len(episodes)} CORE episodes."
        )

    prepared = []

    for index, (episode, events) in enumerate(
        zip(episodes, groups),
        start=1
    ):

        if not events:

            raise RuntimeError(
                "Empty RAW event group for episode "
                f"{episode.get('episode_id')}"
            )

        if (
            episode.get("halt_start")
            != events[0].get("halt_start")
        ):

            raise RuntimeError(
                "Episode start mismatch for "
                f"{episode.get('episode_id')}: "
                f"CORE={episode.get('halt_start')}, "
                f"RAW={events[0].get('halt_start')}"
            )

        raw_ids_for_episode = []

        for event in events:

            natural_key = get_raw_natural_key(
                event
            )

            trade_halt_id = raw_ids.get(
                natural_key
            )

            if trade_halt_id is None:

                raise RuntimeError(
                    "Missing RAW id for episode "
                    f"{episode.get('episode_id')} "
                    f"natural key: {natural_key}"
                )

            raw_ids_for_episode.append(
                trade_halt_id
            )

        if len(raw_ids_for_episode) != len(
            set(raw_ids_for_episode)
        ):

            raise RuntimeError(
                "Duplicate RAW id inside CORE episode "
                f"{episode.get('episode_id')}"
            )

        normalized_markets = {
            normalize_market(
                event.get("market")
            )
            for event in events
            if normalize_market(
                event.get("market")
            ) is not None
        }

        if len(normalized_markets) == 1:

            core_market = next(
                iter(normalized_markets)
            )

        elif len(normalized_markets) == 0:

            core_market = None

        else:

            core_market = None

        reason_codes = {
            empty_to_none(
                event.get("reason_code")
            )
            for event in events
            if empty_to_none(
                event.get("reason_code")
            ) is not None
        }

        if len(reason_codes) == 1:

            core_reason_code = next(
                iter(reason_codes)
            )

        else:

            core_reason_code = None

        issue_names = {
            empty_to_none(
                event.get("issue_name")
            )
            for event in events
            if empty_to_none(
                event.get("issue_name")
            ) is not None
        }

        if len(issue_names) == 1:

            core_issue_name = next(
                iter(issue_names)
            )

        else:

            core_issue_name = None

        prepared.append(
            {
                "episode": episode,
                "events": events,
                "raw_ids": raw_ids_for_episode,
                "market": core_market,
                "reason_code": core_reason_code,
                "issue_name": core_issue_name,
            }
        )

    return prepared


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

    V0.9-A :
    - lookup des natural keys en batch;
    - classification INSERT / UPDATE / UNCHANGED en Python;
    - INSERT SQL réellement batché;
    - UPDATE SQL réellement batché;
    - récupération des IDs avec RETURNING;
    - conservation des règles métier V0.8.

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

    inserted = 0
    updated = 0
    unchanged = 0

    raw_ids = {}

    if not unique_events:
        return (
            inserted,
            updated,
            unchanged,
            raw_ids
        )

    # ========================================================
    # 1. PRÉPARATION ET VALIDATION
    # ========================================================

    prepared_events = []
    seen_natural_keys = set()

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

        natural_key = get_raw_natural_key(
            event
        )

        if natural_key in seen_natural_keys:

            raise RuntimeError(
                "Duplicate RAW natural key "
                "detected in unique_events: "
                f"{natural_key}"
            )

        seen_natural_keys.add(
            natural_key
        )

        prepared_events.append(
            (
                natural_key,
                params
            )
        )

    # ========================================================
    # 2. LOOKUP BATCH DES NATURAL KEYS EXISTANTES
    # ========================================================

    existing_by_key = {}

    lookup_keys = [
        natural_key
        for natural_key, _ in prepared_events
    ]

    # 7 colonnes de natural key.
    # 5 000 × 7 = 35 000 paramètres.
    LOOKUP_BATCH_SIZE = 5000

    with conn.cursor() as cur:

        for batch_start in range(
            0,
            len(lookup_keys),
            LOOKUP_BATCH_SIZE
        ):

            batch_keys = lookup_keys[
                batch_start:
                batch_start + LOOKUP_BATCH_SIZE
            ]

            placeholders = ", ".join(
                ["(%s, %s, %s, %s, %s, %s, %s)"]
                * len(batch_keys)
            )

            lookup_params = []

            for key in batch_keys:
                lookup_params.extend(
                    key
                )

            cur.execute(
                f"""
                SELECT
                    id,
                    symbol,
                    halt_date,
                    halt_time,
                    reason_code,
                    market,
                    issue_name,
                    resumption_date,
                    resumption_quote_time,
                    resumption_trade_time,
                    pause_threshold_price,
                    source_file
                FROM raw.nasdaq_trade_halt
                WHERE (
                    symbol,
                    halt_date,
                    halt_time,
                    reason_code,
                    market,
                    resumption_date,
                    resumption_trade_time
                ) IN ({placeholders});
                """,
                lookup_params
            )

            for row in cur.fetchall():

                (
                    raw_id,
                    symbol,
                    halt_date,
                    halt_time,
                    reason_code,
                    market,
                    issue_name,
                    resumption_date,
                    resumption_quote_time,
                    resumption_trade_time,
                    pause_threshold_price,
                    source_file,
                ) = row

                natural_key = (
                    symbol,
                    halt_date,
                    halt_time,
                    reason_code,
                    market,
                    resumption_date,
                    resumption_trade_time,
                )

                existing_by_key[
                    natural_key
                ] = {
                    "id":
                        raw_id,

                    "issue_name":
                        issue_name,

                    "resumption_date":
                        resumption_date,

                    "resumption_quote_time":
                        resumption_quote_time,

                    "resumption_trade_time":
                        resumption_trade_time,

                    "pause_threshold_price":
                        pause_threshold_price,

                    "source_file":
                        source_file,
                }

    # ========================================================
    # 3. CLASSIFICATION
    # ========================================================

    insert_rows = []
    update_rows = []

    for natural_key, params in prepared_events:

        existing = existing_by_key.get(
            natural_key
        )

        # ----------------------------------------------------
        # NOUVEL ÉVÉNEMENT
        # ----------------------------------------------------

        if existing is None:

            insert_rows.append(
                (
                    natural_key,
                    params
                )
            )

            continue

        raw_id = existing["id"]

        raw_ids[
            natural_key
        ] = raw_id

        # ----------------------------------------------------
        # RÈGLES V0.8
        # ----------------------------------------------------

        desired_issue_name = (
            prefer_new_value(
                existing["issue_name"],
                params["issue_name"]
            )
        )

        desired_resumption_date = (
            prefer_new_value(
                existing["resumption_date"],
                params["resumption_date"]
            )
        )

        desired_resumption_quote_time = (
            prefer_new_value(
                existing[
                    "resumption_quote_time"
                ],
                params[
                    "resumption_quote_time"
                ]
            )
        )

        desired_resumption_trade_time = (
            prefer_new_value(
                existing[
                    "resumption_trade_time"
                ],
                params[
                    "resumption_trade_time"
                ]
            )
        )

        desired_pause_threshold_price = (
            prefer_new_value(
                existing[
                    "pause_threshold_price"
                ],
                params[
                    "pause_threshold_price"
                ]
            )
        )

        has_changes = any(
            (
                desired_issue_name
                != existing["issue_name"],

                desired_resumption_date
                != existing["resumption_date"],

                desired_resumption_quote_time
                != existing[
                    "resumption_quote_time"
                ],

                desired_resumption_trade_time
                != existing[
                    "resumption_trade_time"
                ],

                desired_pause_threshold_price
                != existing[
                    "pause_threshold_price"
                ],
            )
        )

        if has_changes:

            update_rows.append(
                {
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
            )

        else:

            unchanged += 1

        # V0.8 :
        # existing_source_file est volontairement conservé.
        _ = existing["source_file"]

    # ========================================================
    # 4. INSERT BATCH
    # ========================================================

    INSERT_BATCH_SIZE = 5000

    for batch_start in range(
        0,
        len(insert_rows),
        INSERT_BATCH_SIZE
    ):

        batch_rows = insert_rows[
            batch_start:
            batch_start + INSERT_BATCH_SIZE
        ]

        value_placeholders = ", ".join(
            [
                "("
                "%s, %s, %s, %s, %s, %s, "
                "%s, %s, %s, %s, %s"
                ")"
            ]
            * len(batch_rows)
        )

        insert_params = []

        for _, params in batch_rows:

            insert_params.extend(
                [
                    params["symbol"],
                    params["issue_name"],
                    params["market"],
                    params["reason_code"],
                    params["halt_date"],
                    params["halt_time"],
                    params["resumption_date"],
                    params[
                        "resumption_quote_time"
                    ],
                    params[
                        "resumption_trade_time"
                    ],
                    params[
                        "pause_threshold_price"
                    ],
                    params["source_file"],
                ]
            )

        with conn.cursor() as cur:

            cur.execute(
                f"""
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
                VALUES {value_placeholders}
                RETURNING
                    id,
                    symbol,
                    halt_date,
                    halt_time,
                    reason_code,
                    market,
                    resumption_date,
                    resumption_trade_time;
                """,
                insert_params
            )

            returned_rows = cur.fetchall()

        returned_by_key = {}

        for row in returned_rows:

            (
                raw_id,
                symbol,
                halt_date,
                halt_time,
                reason_code,
                market,
                resumption_date,
                resumption_trade_time,
            ) = row

            natural_key = (
                symbol,
                halt_date,
                halt_time,
                reason_code,
                market,
                resumption_date,
                resumption_trade_time,
            )

            returned_by_key[
                natural_key
            ] = raw_id

        for natural_key, _ in batch_rows:

            raw_id = returned_by_key.get(
                natural_key
            )

            if raw_id is None:

                raise RuntimeError(
                    "RAW INSERT did not return an id: "
                    f"{natural_key}"
                )

            raw_ids[
                natural_key
            ] = raw_id

        inserted += len(
            batch_rows
        )

    # ========================================================
    # 5. UPDATE BATCH
    # ========================================================
    #
    # UPDATE via VALUES permet un seul appel SQL par lot.
    # loaded_at n'est volontairement PAS modifié.
    #

    UPDATE_BATCH_SIZE = 5000

    for batch_start in range(
        0,
        len(update_rows),
        UPDATE_BATCH_SIZE
    ):

        batch_rows = update_rows[
            batch_start:
            batch_start + UPDATE_BATCH_SIZE
        ]

        value_placeholders = ", ".join(
            ["(%s, %s, %s, %s, %s, %s)"]
            * len(batch_rows)
        )

        update_params = []

        for row in batch_rows:

            update_params.extend(
                [
                    row["id"],
                    row["issue_name"],
                    row["resumption_date"],
                    row["resumption_quote_time"],
                    row["resumption_trade_time"],
                    row["pause_threshold_price"],
                ]
            )

        with conn.cursor() as cur:

            cur.execute(
                f"""
                UPDATE raw.nasdaq_trade_halt AS target
                SET
                    issue_name = batch.issue_name,
                    resumption_date =
                        batch.resumption_date,
                    resumption_quote_time =
                        batch.resumption_quote_time,
                    resumption_trade_time =
                        batch.resumption_trade_time,
                    pause_threshold_price =
                        batch.pause_threshold_price
                FROM (
                    VALUES {value_placeholders}
                ) AS batch (
                    id,
                    issue_name,
                    resumption_date,
                    resumption_quote_time,
                    resumption_trade_time,
                    pause_threshold_price
                )
                WHERE target.id = batch.id
                RETURNING target.id;
                """,
                update_params
            )

            returned_update_ids = {
                row[0]
                for row in cur.fetchall()
            }

        expected_update_ids = {
            row["id"]
            for row in batch_rows
        }

        if returned_update_ids != expected_update_ids:

            missing_ids = (
                expected_update_ids
                - returned_update_ids
            )

            unexpected_ids = (
                returned_update_ids
                - expected_update_ids
            )

            raise RuntimeError(
                "Unexpected RAW UPDATE result: "
                f"missing={sorted(missing_ids)[:10]}, "
                f"unexpected={sorted(unexpected_ids)[:10]}"
            )

        updated += len(
            batch_rows
        )

    # ========================================================
    # 6. VALIDATION DU CONTRAT
    # ========================================================

    if len(raw_ids) != len(
        prepared_events
    ):

        missing_keys = [
            natural_key
            for natural_key, _ in prepared_events
            if natural_key not in raw_ids
        ]

        raise RuntimeError(
            "RAW IDs missing after batch persistence: "
            f"{missing_keys[:10]}"
        )

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
    Persiste les épisodes CORE et leurs relations CORE -> RAW.

    V1.1 PERFORMANCE :
    - préparation CORE/RAW identique à V1.0;
    - staging PostgreSQL temporaire;
    - INSERT CORE en une opération SQL;
    - UPDATE CORE en une opération SQL;
    - INSERT/DELETE des relations CORE -> RAW en opérations SQL
      massives;
    - aucun SELECT/UPDATE/INSERT individuel par épisode.

    Modèle :
        1 CORE episode -> N RAW events

    Clé naturelle CORE V1.2 :
        symbol
        market
        halt_start

    reason_code est descriptif et ne fait pas partie de la clé.
    """

    if not episodes:
        return (0, 0, 0)

    # ========================================================
    # 1. PRÉPARATION ET VALIDATION EN MÉMOIRE
    # ========================================================

    prepared_groups = _prepare_episode_raw_groups(
        episodes,
        unique_events,
        raw_ids,
    )

    prepared_episodes = []

    for group in prepared_groups:

        episode = group["episode"]
        halt_start = episode.get("halt_start")

        if halt_start is None:
            raise ValueError(
                "CORE episode has no halt_start: "
                f"{episode}"
            )

        episode_raw_ids = list(group["raw_ids"])

        if not episode_raw_ids:
            raise RuntimeError(
                "CORE episode has no RAW ids: "
                f"{episode.get('episode_id')}"
            )

        # ----------------------------------------------------
        # V1.1 DATA QUALITY GUARD
        #
        # Certains snapshots historiques Nasdaq contiennent un
        # resumption_time antérieur au halt_start. Le RAW doit
        # rester fidèle à la source, mais un épisode CORE ne peut
        # pas violer chk_nasdaq_halt_end.
        #
        # Dans ce cas :
        #   - halt_end = NULL
        #   - duration_minutes = NULL
        #   - le RAW et la relation CORE -> RAW sont conservés
        #   - halt_at_close est conservé comme calculé par le
        #     moteur d'épisodes.
        #
        # Exemple historique connu :
        #   TPC / 2023-05-01 / 12:54:10 -> 12:53:43
        # ----------------------------------------------------

        halt_end = episode.get("halt_end")

        if (
            halt_end is not None
            and halt_end < halt_start
        ):
            halt_end = None
            duration_minutes = None
        else:
            duration_minutes = parse_decimal(
                episode.get("duration_minutes")
            )

        prepared_episodes.append(
            {
                "trade_halt_id": episode_raw_ids[0],
                "collector_episode_id":
                    empty_to_none(
                        episode.get("episode_id")
                    ),
                "symbol": episode["symbol"],
                "issue_name": group["issue_name"],
                "market": group["market"],
                "reason_code": group["reason_code"],
                "halt_start": halt_start,
                "halt_end": halt_end,
                "duration_minutes":
                    duration_minutes,
                "halt_close_status":
                    parse_halt_close_status(
                        episode.get("halt_at_close")
                    ),
                "raw_ids": episode_raw_ids,
            }
        )

    seen_raw_ids = set()

    for params in prepared_episodes:

        for trade_halt_id in params["raw_ids"]:

            if trade_halt_id in seen_raw_ids:
                raise RuntimeError(
                    "RAW event assigned to multiple CORE "
                    f"episodes: {trade_halt_id}"
                )

            seen_raw_ids.add(trade_halt_id)

    # ========================================================
    # 2. TEMPORARY STAGING
    #
    # Les types sont dérivés directement du schéma PostgreSQL
    # afin de ne pas supposer int/bigint/timestamp précis.
    # ========================================================

    with conn.cursor() as cur:

        cur.execute(
            """
            CREATE TEMP TABLE _quantlab_core_episode_stage
            ON COMMIT DROP
            AS
            SELECT
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
            FROM core.nasdaq_halt_episode
            WHERE FALSE;
            """
        )

        cur.execute(
            """
            CREATE TEMP TABLE _quantlab_core_relation_stage
            ON COMMIT DROP
            AS
            SELECT
                ep.symbol,
                ep.market,
                ep.halt_start,
                rel.trade_halt_id
            FROM core.nasdaq_halt_episode ep
            JOIN core.nasdaq_halt_episode_event rel
              ON rel.episode_id = ep.id
            WHERE FALSE;
            """
        )

        # executemany() est utilisé uniquement pour charger les tables
        # temporaires. Les opérations CORE réelles restent massives.
        cur.executemany(
            """
            INSERT INTO _quantlab_core_episode_stage (
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
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            );
            """,
            [
                (
                    p["trade_halt_id"],
                    p["collector_episode_id"],
                    p["symbol"],
                    p["issue_name"],
                    p["market"],
                    p["reason_code"],
                    p["halt_start"],
                    p["halt_end"],
                    p["duration_minutes"],
                    p["halt_close_status"],
                )
                for p in prepared_episodes
            ],
        )

        relation_rows = []

        for p in prepared_episodes:

            for trade_halt_id in p["raw_ids"]:

                relation_rows.append(
                    (
                        p["symbol"],
                        p["market"],
                        p["halt_start"],
                        trade_halt_id,
                    )
                )

        cur.executemany(
            """
            INSERT INTO _quantlab_core_relation_stage (
                symbol,
                market,
                halt_start,
                trade_halt_id
            )
            VALUES (%s, %s, %s, %s);
            """,
            relation_rows,
        )

        # ====================================================
        # 3. INTÉGRITÉ DE LA CLÉ CORE
        # ====================================================

        cur.execute(
            """
            SELECT
                s.symbol,
                s.market,
                s.reason_code,
                s.halt_start,
                COUNT(ep.id)
            FROM _quantlab_core_episode_stage s
            JOIN core.nasdaq_halt_episode ep
              ON ep.symbol = s.symbol
             AND ep.market = s.market
             AND ep.halt_start = s.halt_start
            GROUP BY
                s.symbol,
                s.market,
                s.reason_code,
                s.halt_start
            HAVING COUNT(ep.id) > 1;
            """
        )

        duplicate_existing = cur.fetchall()

        if duplicate_existing:

            raise RuntimeError(
                "Multiple CORE episodes found for the same "
                "(symbol, market, halt_start): "
                f"{duplicate_existing[:20]}"
            )

        # ====================================================
        # 4. INSERT CORE MASSIF
        # ====================================================

        cur.execute(
            """
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
            SELECT
                s.trade_halt_id,
                s.collector_episode_id,
                s.symbol,
                s.issue_name,
                s.market,
                s.reason_code,
                s.halt_start,
                s.halt_end,
                s.duration_minutes,
                s.halt_close_status
            FROM _quantlab_core_episode_stage s
            WHERE NOT EXISTS (
                SELECT 1
                FROM core.nasdaq_halt_episode ep
                WHERE ep.symbol = s.symbol
                  AND ep.market = s.market
                  AND ep.halt_start = s.halt_start
            );
            """
        )

        inserted = cur.rowcount

        # ====================================================
        # 5. UPDATE CORE MASSIF
        #
        # prefer_new_value :
        #     incoming NULL -> existing
        #     incoming value -> incoming
        #
        # prefer_close_status :
        #     incoming NULL -> existing
        #     incoming UNKNOWN + existing final -> existing
        #     sinon incoming
        # ====================================================

        cur.execute(
            """
            WITH desired AS (
                SELECT
                    ep.id,
                    CASE
                        WHEN s.issue_name IS NULL
                            THEN ep.issue_name
                        ELSE s.issue_name
                    END AS issue_name_new,
                    CASE
                        WHEN s.market IS NULL
                            THEN ep.market
                        ELSE s.market
                    END AS market_new,
                    CASE
                        WHEN s.reason_code IS NULL
                            THEN ep.reason_code
                        ELSE s.reason_code
                    END AS reason_code_new,
                    CASE
                        WHEN s.halt_end IS NULL
                            THEN ep.halt_end
                        ELSE s.halt_end
                    END AS halt_end_new,
                    CASE
                        WHEN s.duration_minutes IS NULL
                            THEN ep.duration_minutes
                        ELSE s.duration_minutes
                    END AS duration_minutes_new,
                    CASE
                        WHEN s.halt_close_status IS NULL
                            THEN ep.halt_close_status
                        WHEN s.halt_close_status = 'UNKNOWN'
                             AND ep.halt_close_status IN (
                                 'YES',
                                 'NO',
                                 'MULTI_DAY'
                             )
                            THEN ep.halt_close_status
                        ELSE s.halt_close_status
                    END AS halt_close_status_new
                FROM core.nasdaq_halt_episode ep
                JOIN _quantlab_core_episode_stage s
                  ON s.symbol = ep.symbol
                 AND s.market = ep.market
                 AND s.reason_code = ep.reason_code
                 AND s.halt_start = ep.halt_start
            )
            UPDATE core.nasdaq_halt_episode ep
            SET
                issue_name = d.issue_name_new,
                market = d.market_new,
                reason_code = d.reason_code_new,
                halt_end = d.halt_end_new,
                duration_minutes = d.duration_minutes_new,
                halt_close_status = d.halt_close_status_new
            FROM desired d
            WHERE ep.id = d.id
              AND (
                  ep.issue_name IS DISTINCT FROM d.issue_name_new
                  OR ep.market IS DISTINCT FROM d.market_new
                  OR ep.reason_code IS DISTINCT FROM d.reason_code_new
                  OR ep.halt_end IS DISTINCT FROM d.halt_end_new
                  OR ep.duration_minutes
                      IS DISTINCT FROM d.duration_minutes_new
                  OR ep.halt_close_status
                      IS DISTINCT FROM d.halt_close_status_new
              );
            """
        )

        updated = cur.rowcount

        expected = len(prepared_episodes)

        unchanged = expected - inserted - updated

        if unchanged < 0:
            raise RuntimeError(
                "CORE persistence count mismatch: "
                f"inserted={inserted}, "
                f"updated={updated}, "
                f"expected={expected}"
            )

        # ====================================================
        # 6. SUPPRESSION DES RELATIONS OBSOLÈTES
        #
        # Seulement pour les épisodes présents dans le staging.
        # ====================================================

        cur.execute(
            """
            DELETE FROM core.nasdaq_halt_episode_event rel
            USING core.nasdaq_halt_episode ep
            JOIN _quantlab_core_episode_stage s
              ON s.symbol = ep.symbol
             AND s.market = ep.market
             AND s.reason_code = ep.reason_code
             AND s.halt_start = ep.halt_start
            WHERE rel.episode_id = ep.id
              AND NOT EXISTS (
                  SELECT 1
                  FROM _quantlab_core_relation_stage desired
                  WHERE desired.symbol = ep.symbol
                    AND desired.market = ep.market
                    AND desired.halt_start = ep.halt_start
                    AND desired.trade_halt_id = rel.trade_halt_id
              );
            """
        )

        # ====================================================
        # 7. INSERT DES RELATIONS MANQUANTES EN MASSE
        # ====================================================

        cur.execute(
            """
            INSERT INTO core.nasdaq_halt_episode_event (
                episode_id,
                trade_halt_id
            )
            SELECT
                ep.id,
                desired.trade_halt_id
            FROM _quantlab_core_relation_stage desired
            JOIN core.nasdaq_halt_episode ep
              ON ep.symbol = desired.symbol
             AND ep.market = desired.market
             AND ep.halt_start = desired.halt_start
            WHERE NOT EXISTS (
                SELECT 1
                FROM core.nasdaq_halt_episode_event rel
                WHERE rel.episode_id = ep.id
                  AND rel.trade_halt_id = desired.trade_halt_id
            );
            """
        )

        # ====================================================
        # 8. VALIDATION RELATIONNELLE
        #
        # V1.2 :
        # reason_code ne fait pas partie de l'identité CORE.
        # Une relation est identifiée par :
        #
        #     symbol + market + halt_start + trade_halt_id
        #
        # ====================================================

        expected_raw_count = len(seen_raw_ids)

        cur.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT DISTINCT
                    desired.symbol,
                    desired.market,
                    desired.halt_start,
                    desired.trade_halt_id
                FROM _quantlab_core_relation_stage desired
            ) expected
            JOIN core.nasdaq_halt_episode ep
              ON ep.symbol = expected.symbol
             AND ep.market = expected.market
             AND ep.halt_start = expected.halt_start
            JOIN core.nasdaq_halt_episode_event rel
              ON rel.episode_id = ep.id
             AND rel.trade_halt_id = expected.trade_halt_id;
            """
        )

        observed_relationships = cur.fetchone()[0]

        if observed_relationships != expected_raw_count:

            raise RuntimeError(
                "CORE -> RAW relationship validation failed: "
                f"expected={expected_raw_count}, "
                f"observed={observed_relationships}"
            )

    return (
        inserted,
        updated,
        unchanged,
    )
