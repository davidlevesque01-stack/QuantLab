import csv
import json

from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from collectors.nasdaq_halts.src.nasdaq_xml import parse_xml_bytes


# ============================================================
# QUANTLAB - NASDAQ HALT LIVE COLLECTOR
# VERSION 0.8
# ============================================================

VERSION = "0.8"


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "config.json"

with open(
    CONFIG_FILE,
    "r",
    encoding="utf-8"
) as file:

    config = json.load(file)


# ============================================================
# Répertoires
# ============================================================

raw_directory = (
    PROJECT_ROOT
    / config["raw_directory"]
)

live_raw_directory = (
    raw_directory
    / "live"
)

processed_directory = (
    PROJECT_ROOT
    / config["processed_directory"]
)

raw_directory.mkdir(
    parents=True,
    exist_ok=True
)

live_raw_directory.mkdir(
    parents=True,
    exist_ok=True
)

processed_directory.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# Téléchargement du flux Nasdaq
# ============================================================

url = config["nasdaq_rss_base_url"]

request = Request(
    url,
    headers={
        "User-Agent":
            config["user_agent"]
    }
)

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

print(
    "Téléchargement du flux Nasdaq..."
)

with urlopen(
    request,
    timeout=config["request_timeout_seconds"]
) as response:

    xml_data = response.read()

print(
    f"Flux reçu : {len(xml_data)} octets"
)


# ============================================================
# Snapshot XML immuable
# ============================================================

collection_timestamp = (
    datetime.now(
        timezone.utc
    )
)

timestamp_text = (
    collection_timestamp.strftime(
        "%Y%m%dT%H%M%SZ"
    )
)

snapshot_file = (
    live_raw_directory
    / f"tradehalts_live_{timestamp_text}.xml"
)

with open(
    snapshot_file,
    "wb"
) as file:

    file.write(
        xml_data
    )

print(
    f"Snapshot XML : {snapshot_file}"
)


# ============================================================
# Copie latest
# ============================================================

latest_file = (
    raw_directory
    / "latest_tradehalts.xml"
)

with open(
    latest_file,
    "wb"
) as file:

    file.write(
        xml_data
    )

print(
    f"XML latest   : {latest_file}"
)


# ============================================================
# Parsing normalisé
# ============================================================

records = parse_xml_bytes(
    xml_data,
    snapshot_file.name
)

print()
print(
    f"Nombre d'enregistrements trouvés : {len(records)}"
)


# ============================================================
# Affichage de contrôle
# ============================================================

if records:

    print()
    print(
        "Premier enregistrement :"
    )
    print()

    first_record = records[0]

    fields_to_display = [
        "halt_date",
        "halt_time",
        "symbol",
        "issue_name",
        "market",
        "reason_code",
        "pause_threshold_price",
        "resumption_date",
        "resumption_quote_time",
        "resumption_trade_time",
        "halt_start",
        "halt_end",
        "source_file",
    ]

    for field in fields_to_display:

        print(
            f"{field}: "
            f"{first_record[field]}"
        )

else:

    print()
    print(
        "Aucun HALT présent dans le flux."
    )


# ============================================================
# Export CSV live secondaire
# ============================================================

live_csv_file = (
    processed_directory
    / "live_tradehalts.csv"
)

fieldnames = [
    "halt_date",
    "halt_time",
    "symbol",
    "issue_name",
    "market",
    "reason_code",
    "pause_threshold_price",
    "resumption_date",
    "resumption_quote_time",
    "resumption_trade_time",
]

with open(
    live_csv_file,
    "w",
    newline="",
    encoding="utf-8-sig"
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=fieldnames,
        extrasaction="ignore"
    )

    writer.writeheader()

    writer.writerows(
        records
    )


# ============================================================
# Résultat
# ============================================================

print()
print(
    f"CSV live créé : {live_csv_file}"
)

print(
    f"Enregistrements exportés : {len(records)}"
)

print()

print(
    "============================================================"
)

print(
    f"COLLECTE LIVE V{VERSION} TERMINÉE"
)

print(
    "============================================================"
)
