from datetime import datetime, time
from decimal import Decimal
from typing import Any

from shared.database import get_connection


# ============================================================
# QuantLab - Nasdaq PostgreSQL Persistence
# VERSION 1.0
# ============================================================

VERSION = "1.0"

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
    build_halt_episodes().

    Important :
    - le regroupement demeure effectué par symbole;
    - les alias de marché ne créent pas un nouvel épisode;
    - un événement appartient à un seul groupe;
    - la liste retournée conserve l'ordre de construction des épisodes.
    """

    from collections import defaultdict

    events_by_symbol = defaultdict(list)

    for event in unique_events:

        if event.get("halt_start") is not None:

            events_by_symbol[
                event["symbol"]
            ].append(event)

    groups = []

    for symbol, events in events_by_symbol.items():

        events.sort(
            key=lambda x: x["halt_start"]
        )

        current_events = []
        current_start = None
        current_end = None

        for event in events:

            start = event["halt_start"]
            end = event["halt_end"]

            if not current_events:

                current_events = [event]
                current_start = start
                current_end = end
                continue

            same_episode = False

            if start == current_start:

                same_episode = True

            elif (
                current_end is not None
                and start <= current_end
            ):

                same_episode = True

            if same_episode:

                current_events.append(event)

                if start < current_start:
                    current_start = start

                if end is not None:

                    if (
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

    # 5 colonnes de natural key.
    # 5 000 × 5 = 25 000 paramètres.
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
                ["(%s, %s, %s, %s, %s)"]
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
                    market
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
                    market;
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
            ) = row

            natural_key = (
                symbol,
                halt_date,
                halt_time,
                reason_code,
                market,
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
    Écrit les HALT Episodes dans :

        core.nasdaq_halt_episode

    Modèle V1.0 :

        1 CORE episode -> N RAW events

    La table :

        core.nasdaq_halt_episode_event

    conserve toutes les relations CORE -> RAW.

    Règles :
    - les épisodes sont reconstruits selon la logique validée de
      build_halt_episodes();
    - les alias Q/N/A et leurs noms complets sont normalisés pour
      déterminer le marché CORE;
    - plusieurs marchés normalisés => market = NULL;
    - plusieurs reason_code => reason_code = NULL;
    - un épisode peut référencer plusieurs RAW events;
    - trade_halt_id conserve un RAW représentatif pour compatibilité
      avec le schéma CORE historique;
    - une même RAW event ne peut appartenir qu'à un seul CORE;
    - les écritures sont idempotentes;
    - les valeurs NULL entrantes n'effacent pas une valeur connue.
    """

    inserted = 0
    updated = 0
    unchanged = 0

    if not episodes:

        return (
            inserted,
            updated,
            unchanged,
        )

    # ========================================================
    # 1. PRÉPARATION DES GROUPES CORE -> RAW
    # ========================================================

    prepared_groups = _prepare_episode_raw_groups(
        episodes,
        unique_events,
        raw_ids,
    )

    prepared_episodes = []

    for group in prepared_groups:

        episode = group["episode"]

        halt_start = episode.get(
            "halt_start"
        )

        if halt_start is None:

            raise ValueError(
                "CORE episode has no halt_start: "
                f"{episode}"
            )

        params = {
            # Legacy representative RAW id retained because the
            # existing CORE schema still requires trade_halt_id
            # and enforces UNIQUE(trade_halt_id). The complete
            # 1-to-N relationship is stored in
            # core.nasdaq_halt_episode_event.
            "trade_halt_id":
                raw_ids_for_episode[0],

            "collector_episode_id":
                empty_to_none(
                    episode.get(
                        "episode_id"
                    )
                ),

            "symbol":
                episode["symbol"],

            "issue_name":
                group["issue_name"],

            "market":
                group["market"],

            "reason_code":
                group["reason_code"],

            "halt_start":
                halt_start,

            "halt_end":
                episode.get(
                    "halt_end"
                ),

            "duration_minutes":
                parse_decimal(
                    episode.get(
                        "duration_minutes"
                    )
                ),

            "halt_close_status":
                parse_halt_close_status(
                    episode.get(
                        "halt_at_close"
                    )
                ),

            "raw_ids":
                group["raw_ids"],
        }

        prepared_episodes.append(
            params
        )

    # ========================================================
    # 2. VALIDATION RAW -> CORE
    # ========================================================

    seen_raw_ids = set()

    for params in prepared_episodes:

        for trade_halt_id in params["raw_ids"]:

            if trade_halt_id in seen_raw_ids:

                raise RuntimeError(
                    "RAW event assigned to multiple CORE "
                    f"episodes: {trade_halt_id}"
                )

            seen_raw_ids.add(
                trade_halt_id
            )

    # ========================================================
    # 3. LOOKUP CORE PAR HALT_START + SYMBOL
    #
    # trade_halt_id n'est plus la clé unique d'un épisode.
    # ========================================================

    existing_by_key = {}

    with conn.cursor() as cur:

        for params in prepared_episodes:

            cur.execute(
                """
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
                WHERE symbol = %s
                  AND halt_start = %s;
                """,
                (
                    params["symbol"],
                    params["halt_start"],
                )
            )

            rows = cur.fetchall()

            if len(rows) > 1:

                raise RuntimeError(
                    "Multiple CORE episodes found for "
                    f"{params['symbol']} at "
                    f"{params['halt_start']}."
                )

            if rows:

                row = rows[0]

                existing_by_key[
                    (
                        params["symbol"],
                        params["halt_start"],
                    )
                ] = {
                    "id": row[0],
                    "collector_episode_id": row[1],
                    "symbol": row[2],
                    "issue_name": row[3],
                    "market": row[4],
                    "reason_code": row[5],
                    "halt_start": row[6],
                    "halt_end": row[7],
                    "duration_minutes": row[8],
                    "halt_close_status": row[9],
                }

    # ========================================================
    # 4. CLASSIFICATION
    # ========================================================

    insert_rows = []
    update_rows = []

    for params in prepared_episodes:

        key = (
            params["symbol"],
            params["halt_start"],
        )

        existing = existing_by_key.get(
            key
        )

        if existing is None:

            insert_rows.append(
                params
            )

            continue

        episode_id = existing["id"]

        if (
            existing["symbol"]
            != params["symbol"]
        ):

            raise RuntimeError(
                "CORE symbol mismatch for "
                f"episode id {episode_id}"
            )

        if (
            existing["halt_start"]
            != params["halt_start"]
        ):

            raise RuntimeError(
                "CORE halt_start mismatch for "
                f"episode id {episode_id}"
            )

        desired_issue_name = (
            prefer_new_value(
                existing["issue_name"],
                params["issue_name"]
            )
        )

        desired_market = (
            prefer_new_value(
                existing["market"],
                params["market"]
            )
        )

        desired_reason_code = (
            prefer_new_value(
                existing["reason_code"],
                params["reason_code"]
            )
        )

        desired_halt_end = (
            prefer_new_value(
                existing["halt_end"],
                params["halt_end"]
            )
        )

        desired_duration_minutes = (
            prefer_new_value(
                existing["duration_minutes"],
                params["duration_minutes"]
            )
        )

        desired_halt_close_status = (
            prefer_close_status(
                existing["halt_close_status"],
                params["halt_close_status"]
            )
        )

        has_changes = any(
            (
                desired_issue_name
                != existing["issue_name"],

                desired_market
                != existing["market"],

                desired_reason_code
                != existing["reason_code"],

                desired_halt_end
                != existing["halt_end"],

                desired_duration_minutes
                != existing["duration_minutes"],

                desired_halt_close_status
                != existing["halt_close_status"],
            )
        )

        if has_changes:

            update_rows.append(
                {
                    "id": episode_id,
                    "issue_name": desired_issue_name,
                    "market": desired_market,
                    "reason_code": desired_reason_code,
                    "halt_end": desired_halt_end,
                    "duration_minutes":
                        desired_duration_minutes,
                    "halt_close_status":
                        desired_halt_close_status,
                    "raw_ids":
                        params["raw_ids"],
                }
            )

        else:

            update_rows.append(
                {
                    "id": episode_id,
                    "issue_name":
                        existing["issue_name"],
                    "market":
                        existing["market"],
                    "reason_code":
                        existing["reason_code"],
                    "halt_end":
                        existing["halt_end"],
                    "duration_minutes":
                        existing["duration_minutes"],
                    "halt_close_status":
                        existing["halt_close_status"],
                    "raw_ids":
                        params["raw_ids"],
                }
            )

            unchanged += 1

    # ========================================================
    # 5. INSERT CORE + RELATIONS
    # ========================================================

    for params in insert_rows:

        with conn.cursor() as cur:

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
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                RETURNING id;
                """,
                (
                    params["trade_halt_id"],
                    params["collector_episode_id"],
                    params["symbol"],
                    params["issue_name"],
                    params["market"],
                    params["reason_code"],
                    params["halt_start"],
                    params["halt_end"],
                    params["duration_minutes"],
                    params["halt_close_status"],
                )
            )

            episode_id = cur.fetchone()[0]

            for trade_halt_id in params["raw_ids"]:

                cur.execute(
                    """
                    INSERT INTO core.nasdaq_halt_episode_event (
                        episode_id,
                        trade_halt_id
                    )
                    VALUES (%s, %s)
                    ON CONFLICT (
                        episode_id,
                        trade_halt_id
                    )
                    DO NOTHING;
                    """,
                    (
                        episode_id,
                        trade_halt_id,
                    )
                )

        inserted += 1

    # ========================================================
    # 6. UPDATE CORE + RECONSTRUCTION DES RELATIONS
    # ========================================================

    for row in update_rows:

        with conn.cursor() as cur:

            cur.execute(
                """
                UPDATE core.nasdaq_halt_episode
                SET
                    issue_name = %s,
                    market = %s,
                    reason_code = %s,
                    halt_end = %s,
                    duration_minutes = %s,
                    halt_close_status = %s
                WHERE id = %s
                RETURNING id;
                """,
                (
                    row["issue_name"],
                    row["market"],
                    row["reason_code"],
                    row["halt_end"],
                    row["duration_minutes"],
                    row["halt_close_status"],
                    row["id"],
                )
            )

            returned_id = cur.fetchone()

            if returned_id is None:

                raise RuntimeError(
                    "CORE UPDATE did not return episode id "
                    f"{row['id']}"
                )

            cur.execute(
                """
                SELECT
                    trade_halt_id
                FROM core.nasdaq_halt_episode_event
                WHERE episode_id = %s;
                """,
                (row["id"],)
            )

            existing_raw_ids = {
                result[0]
                for result in cur.fetchall()
            }

            desired_raw_ids = set(
                row["raw_ids"]
            )

            extra_raw_ids = (
                existing_raw_ids
                - desired_raw_ids
            )

            missing_raw_ids = (
                desired_raw_ids
                - existing_raw_ids
            )

            for trade_halt_id in extra_raw_ids:

                cur.execute(
                    """
                    DELETE FROM core.nasdaq_halt_episode_event
                    WHERE episode_id = %s
                      AND trade_halt_id = %s;
                    """,
                    (
                        row["id"],
                        trade_halt_id,
                    )
                )

            for trade_halt_id in missing_raw_ids:

                cur.execute(
                    """
                    INSERT INTO core.nasdaq_halt_episode_event (
                        episode_id,
                        trade_halt_id
                    )
                    VALUES (%s, %s)
                    ON CONFLICT (
                        episode_id,
                        trade_halt_id
                    )
                    DO NOTHING;
                    """,
                    (
                        row["id"],
                        trade_halt_id,
                    )
                )

    # ========================================================
    # 7. VALIDATION FINALE
    # ========================================================

    expected_count = len(
        prepared_episodes
    )

    if (
        inserted
        + updated
        + unchanged
        != expected_count
    ):

        raise RuntimeError(
            "CORE persistence count mismatch: "
            f"inserted={inserted}, "
            f"updated={updated}, "
            f"unchanged={unchanged}, "
            f"expected={expected_count}"
        )

    # Chaque RAW de cette exécution doit être reliée
    # exactement à un CORE.
    expected_raw_ids = set(
        seen_raw_ids
    )

    if expected_raw_ids:

        with conn.cursor() as cur:

            placeholders = ", ".join(
                ["%s"] * len(expected_raw_ids)
            )

            cur.execute(
                f"""
                SELECT
                    trade_halt_id,
                    COUNT(DISTINCT episode_id)
                FROM core.nasdaq_halt_episode_event
                WHERE trade_halt_id IN (
                    {placeholders}
                )
                GROUP BY trade_halt_id;
                """,
                list(expected_raw_ids)
            )

            relation_counts = {
                row[0]: row[1]
                for row in cur.fetchall()
            }

        missing = [
            raw_id
            for raw_id in expected_raw_ids
            if relation_counts.get(raw_id, 0) != 1
        ]

        if missing:

            raise RuntimeError(
                "CORE -> RAW relationship validation failed. "
                "RAW ids without exactly one CORE relation: "
                f"{missing[:20]}"
            )

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
        puis
        CORE -> RAW relationships

    Toute erreur provoque le rollback de l'ensemble de
    l'opération.
    """

    print()
    print(
        "============================================================"
    )
    print(
        f"POSTGRESQL PERSISTENCE V1.0"
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
        "PostgreSQL persistence completed"
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
