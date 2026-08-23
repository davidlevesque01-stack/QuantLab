import csv
import json
from pathlib import Path
from urllib.request import Request, urlopen
from xml.etree import ElementTree


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config" / "config.json"

with open(CONFIG_FILE, "r", encoding="utf-8") as file:
    config = json.load(file)


# ============================================================
# Téléchargement du flux Nasdaq
# ============================================================

url = config["nasdaq_rss_base_url"]

request = Request(
    url,
    headers={
        "User-Agent": config["user_agent"]
    }
)

print("QuantLab - Nasdaq Halt Collector")
print()
print("Téléchargement du flux Nasdaq...")

with urlopen(
    request,
    timeout=config["request_timeout_seconds"]
) as response:

    xml_data = response.read()

print(f"Flux reçu : {len(xml_data)} octets")


# ============================================================
# Sauvegarde du XML brut
# ============================================================

raw_directory = (
    PROJECT_ROOT
    / config["raw_directory"]
)

raw_directory.mkdir(
    parents=True,
    exist_ok=True
)

raw_file = raw_directory / "latest_tradehalts.xml"

with open(raw_file, "wb") as file:
    file.write(xml_data)

print(f"XML brut : {raw_file}")


# ============================================================
# Analyse du XML
# ============================================================

root = ElementTree.fromstring(xml_data)

namespace = {
    "ndaq": "http://www.nasdaqtrader.com/"
}

items = root.findall("./channel/item")

print()
print(f"Nombre d'enregistrements trouvés : {len(items)}")


# ============================================================
# Extraction des données
# ============================================================

records = []

for item in items:

    def get_value(field):
        element = item.find(f"ndaq:{field}", namespace)

        if element is None or element.text is None:
            return ""

        return element.text.strip()


    record = {
        "halt_date": get_value("HaltDate"),
        "halt_time": get_value("HaltTime"),
        "symbol": get_value("IssueSymbol"),
        "issue_name": get_value("IssueName"),
        "market": get_value("Market"),
        "reason_code": get_value("ReasonCode"),
        "pause_threshold_price": get_value(
            "PauseThresholdPrice"
        ),
        "resumption_date": get_value("ResumptionDate"),
        "resumption_quote_time": get_value(
            "ResumptionQuoteTime"
        ),
        "resumption_trade_time": get_value(
            "ResumptionTradeTime"
        )
    }

    records.append(record)


# ============================================================
# Affichage de contrôle
# ============================================================

print()
print("Premier enregistrement :")
print()

for key, value in records[0].items():
    print(f"{key}: {value}")


# ============================================================
# Export CSV
# ============================================================

processed_directory = (
    PROJECT_ROOT
    / config["processed_directory"]
)

processed_directory.mkdir(
    parents=True,
    exist_ok=True
)

csv_file = processed_directory / "tradehalts.csv"

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
    "resumption_trade_time"
]

with open(
    csv_file,
    "w",
    newline="",
    encoding="utf-8-sig"
) as file:

    writer = csv.DictWriter(
        file,
        fieldnames=fieldnames
    )

    writer.writeheader()
    writer.writerows(records)


print()
print(f"CSV créé : {csv_file}")
print(f"Enregistrements exportés : {len(records)}")