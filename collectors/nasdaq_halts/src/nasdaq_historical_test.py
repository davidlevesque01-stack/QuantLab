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
# Paramètres du test
# ============================================================

halt_date = config["test_historical_date"]

test_symbols = {
    symbol.upper()
    for symbol in config["test_symbols"]
}


# ============================================================
# Construction de l'URL
# ============================================================

url = (
    f'{config["nasdaq_rss_base_url"]}'
    f'&resumedate={halt_date}'
)


print("QuantLab - Nasdaq Historical Test")
print()
print(f"Date recherchée : {halt_date}")
print()
print("Symboles recherchés :")

for symbol in sorted(test_symbols):
    print(f"  {symbol}")

print()
print("Téléchargement...")
print()


# ============================================================
# Requête Nasdaq
# ============================================================

request = Request(
    url,
    headers={
        "User-Agent": config["user_agent"]
    }
)

with urlopen(
    request,
    timeout=config["request_timeout_seconds"]
) as response:

    xml_data = response.read()


print(f"Données reçues : {len(xml_data)} octets")


# ============================================================
# Analyse XML
# ============================================================

root = ElementTree.fromstring(xml_data)

namespace = {
    "ndaq": "http://www.nasdaqtrader.com/"
}

items = root.findall("./channel/item")

print(f"Nombre total de résultats Nasdaq : {len(items)}")
print()
print()
print("Symboles retournés par Nasdaq :")
print()

for item in items:
    element = item.find("ndaq:IssueSymbol", namespace)

    if element is not None and element.text:
        print(element.text.strip())


# ============================================================
# Extraction
# ============================================================

records = []


for item in items:

    def get_value(field):
        element = item.find(
            f"ndaq:{field}",
            namespace
        )

        if element is None or element.text is None:
            return ""

        return element.text.strip()


    record = {
        "symbol": get_value("IssueSymbol"),
        "issue_name": get_value("IssueName"),
        "market": get_value("Mkt"),
        "reason_code": get_value("ReasonCode"),
        "halt_date": get_value("HaltDate"),
        "halt_time": get_value("HaltTime"),
        "pause_threshold_price": get_value(
            "PauseThresholdPrice"
        ),
        "resumption_date": get_value(
            "ResumptionDate"
        ),
        "resumption_quote_time": get_value(
            "ResumptionQuoteTime"
        ),
        "resumption_trade_time": get_value(
            "ResumptionTradeTime"
        )
    }

    records.append(record)


# ============================================================
# Filtrage des quatre symboles
# ============================================================

matches = [
    record
    for record in records
    if record["symbol"].upper() in test_symbols
]


# ============================================================
# Résultats
# ============================================================

print("============================================================")
print("RÉSULTATS")
print("============================================================")
print()

found_symbols = set()

for record in matches:

    symbol = record["symbol"].upper()
    found_symbols.add(symbol)

    print(f"Ticker : {record['symbol']}")
    print(f"Nom    : {record['issue_name']}")
    print(f"Marché : {record['market']}")
    print(f"Code   : {record['reason_code']}")
    print(
        f"Halt   : "
        f"{record['halt_date']} "
        f"{record['halt_time']}"
    )
    print(
        f"Reprise : "
        f"{record['resumption_date']} "
        f"{record['resumption_quote_time']}"
    )
    print()


# ============================================================
# Vérification
# ============================================================

print("============================================================")
print("VÉRIFICATION")
print("============================================================")
print()

for symbol in sorted(test_symbols):

    if symbol in found_symbols:
        print(f"{symbol} : TROUVÉ ✓")
    else:
        print(f"{symbol} : NON TROUVÉ ✗")

print()
print(
    f"{len(found_symbols)} / "
    f"{len(test_symbols)} symboles trouvés."
)