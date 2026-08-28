# ============================================================
# QUANTLAB - NASDAQ HALT LIVE COLLECTOR
# VERSION 0.8
# ============================================================

import csv
import json

from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from collectors.nasdaq_halts.src.nasdaq_xml import (
    parse_xml_bytes,
)

from collectors.nasdaq_halts.src.nasdaq_deduplication import (
    deduplicate_events,
)

from collectors.nasdaq_halts.src.nasdaq_episodes import (
    build_halt_episodes,
)

from collectors.nasdaq_halts.src.nasdaq_postgresql import (
    persist_nasdaq_halts,
)


VERSION = "0.8"

BASE_DIR = Path(__file__).resolve().parent.parent

CONFIG_FILE = (
    BASE_DIR
    / "config"
    / "config.json"
)


# ============================================================
# CONFIGURATION
# ============================================================

def load_config():
    """
    Charge la configuration du collecteur Nasdaq.
    """

    with open(
        CONFIG_FILE,
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


# ============================================================
# TÉLÉCHARGEMENT
# ============================================================

def download_nasdaq_feed(
    url,
    timeout,
    user_agent,
):
    """
    Télécharge le flux RSS Nasdaq courant.
    """

    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
        },
    )

    with urlopen(
        request,
        timeout=timeout,
    ) as response:

        return response.read()


# ============================================================
# SNAPSHOT RAW
# ============================================================

def save_raw_snapshot(
    xml_bytes,
    raw_directory,
):
    """
    Sauvegarde deux représentations du flux reçu.

    1. Snapshot immuable horodaté :
       raw/nasdaq/live/tradehalts_live_<UTC>.xml

    2. Copie pratique du dernier flux :
       raw/nasdaq/latest_tradehalts.xml

    Le snapshot immuable constitue la provenance du lot live.
    """

    live_directory = (
        raw_directory
        / "live"
    )

    live_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    raw_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = (
        datetime.now(timezone.utc)
        .strftime(
            "%Y%m%dT%H%M%SZ"
        )
    )

    snapshot_file = (
        live_directory
        / f"tradehalts_live_{timestamp}.xml"
    )

    latest_file = (
        raw_directory
        / "latest_tradehalts.xml"
    )

    snapshot_file.write_bytes(
        xml_bytes
    )

    latest_file.write_bytes(
        xml_bytes
    )

    return (
        snapshot_file,
        latest_file,
    )


# ============================================================
# EXPORT CSV LIVE
# ============================================================

def export_live_csv(
    events,
    processed_directory,
):
    """
    Exporte le dernier lot live en CSV.

    Ce fichier est uniquement un export pratique/debug.

    Il n'est PAS utilisé comme intermédiaire pour PostgreSQL.
    """

    processed_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_file = (
        processed_directory
        / "live_tradehalts.csv"
    )

    fieldnames = [
        "symbol",
        "issue_name",
        "market",
        "reason_code",
        "halt_date",
        "halt_time",
        "resumption_date",
        "resumption_quote_time",
        "resumption_trade_time",
        "pause_threshold_price",
    ]

    with open(
        csv_file,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )

        writer.writeheader()

        writer.writerows(
            events
        )

    return csv_file


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "============================================================"
    )
    print(
        f"QUANTLAB - NASDAQ HALT LIVE COLLECTOR V{VERSION}"
    )
    print(
        "============================================================"
    )
    print()

    config = load_config()

    nasdaq_url = (
        config[
            "nasdaq_rss_base_url"
        ]
    )

    raw_directory = (
        BASE_DIR
        / config[
            "raw_directory"
        ]
    )

    processed_directory = (
        BASE_DIR
        / config[
            "processed_directory"
        ]
    )

    timeout = config.get(
        "request_timeout_seconds",
        30,
    )

    user_agent = config.get(
        "user_agent",
        "QuantLab Nasdaq Halt Collector/0.8",
    )

    # ========================================================
    # 1. DOWNLOAD
    # ========================================================

    print(
        "Téléchargement du flux Nasdaq..."
    )

    xml_bytes = (
        download_nasdaq_feed(
            nasdaq_url,
            timeout,
            user_agent,
        )
    )

    print(
        f"Flux reçu : {len(xml_bytes)} octets"
    )

    # ========================================================
    # 2. SNAPSHOT XML
    # ========================================================

    (
        snapshot_file,
        latest_file,
    ) = save_raw_snapshot(
        xml_bytes,
        raw_directory,
    )

    print(
        f"Snapshot XML : {snapshot_file}"
    )

    print(
        f"XML latest   : {latest_file}"
    )

    # ========================================================
    # 3. PARSING COMMUN
    # ========================================================

    events = parse_xml_bytes(
        xml_bytes,
        source_file=snapshot_file.name,
    )

    print(
        f"Événements bruts : {len(events)}"
    )

    # ========================================================
    # 4. DÉDUPLICATION
    # ========================================================

    unique_events = (
        deduplicate_events(
            events
        )
    )

    print(
        f"Événements uniques : {len(unique_events)}"
    )

    # ========================================================
    # 5. ZÉRO ÉVÉNEMENT
    # ========================================================

    if not unique_events:

        print()
        print(
            "Aucun HALT présent dans le flux."
        )

        csv_file = (
            export_live_csv(
                [],
                processed_directory,
            )
        )

        print(
            f"CSV live créé : {csv_file}"
        )

        print()
        print(
            "COLLECTE LIVE V0.8 TERMINÉE"
        )

        return

    # ========================================================
    # 6. INFORMATION PREMIER ÉVÉNEMENT
    # ========================================================

    first_event = (
        unique_events[0]
    )

    print()
    print(
        "Premier événement :"
    )

    print(
        f"  symbol          : "
        f"{first_event.get('symbol')}"
    )

    print(
        f"  issue_name      : "
        f"{first_event.get('issue_name')}"
    )

    print(
        f"  market          : "
        f"{first_event.get('market')}"
    )

    print(
        f"  reason_code     : "
        f"{first_event.get('reason_code')}"
    )

    print(
        f"  halt_start      : "
        f"{first_event.get('halt_start')}"
    )

    print(
        f"  halt_end        : "
        f"{first_event.get('halt_end')}"
    )

    print(
        f"  source_file     : "
        f"{first_event.get('source_file')}"
    )

    # ========================================================
    # 7. CONSTRUCTION DES ÉPISODES
    # ========================================================

    (
        episodes,
        episode_statistics,
    ) = build_halt_episodes(
        unique_events
    )

    print()
    print(
        f"HALT Episodes : {len(episodes)}"
    )

    print(
        "Durées calculables : "
        f"{episode_statistics['duration_count']}"
    )

    print(
        "Clôture YES        : "
        f"{episode_statistics['close_yes']}"
    )

    print(
        "Clôture NO         : "
        f"{episode_statistics['close_no']}"
    )

    print(
        "Clôture UNKNOWN    : "
        f"{episode_statistics['close_unknown']}"
    )

    print(
        "Clôture MULTI_DAY  : "
        f"{episode_statistics['close_multi_day']}"
    )

    # ========================================================
    # 8. POSTGRESQL
    # ========================================================

    persistence_result = (
        persist_nasdaq_halts(
            unique_events,
            episodes,
        )
    )

    # ========================================================
    # 9. EXPORT CSV OPTIONNEL
    # ========================================================

    csv_file = (
        export_live_csv(
            unique_events,
            processed_directory,
        )
    )

    print()
    print(
        f"CSV live créé : {csv_file}"
    )

    print(
        f"Enregistrements exportés : "
        f"{len(unique_events)}"
    )

    # ========================================================
    # 10. RÉSUMÉ
    # ========================================================

    print()
    print(
        "============================================================"
    )
    print(
        "RÉSUMÉ LIVE V0.8"
    )
    print(
        "============================================================"
    )

    print(
        f"Événements uniques : "
        f"{len(unique_events)}"
    )

    print(
        f"HALT Episodes      : "
        f"{len(episodes)}"
    )

    print(
        "RAW inserted       : "
        f"{persistence_result['raw_inserted']}"
    )

    print(
        "RAW updated        : "
        f"{persistence_result['raw_updated']}"
    )

    print(
        "RAW unchanged      : "
        f"{persistence_result['raw_unchanged']}"
    )

    print(
        "CORE inserted      : "
        f"{persistence_result['core_inserted']}"
    )

    print(
        "CORE updated       : "
        f"{persistence_result['core_updated']}"
    )

    print(
        "CORE unchanged     : "
        f"{persistence_result['core_unchanged']}"
    )

    print()
    print(
        "COLLECTE LIVE V0.8 TERMINÉE ✓"
    )


if __name__ == "__main__":
    main()
