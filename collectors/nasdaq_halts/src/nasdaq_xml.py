from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET


# ============================================================
# QUANTLAB - NASDAQ XML PARSER
# ============================================================

NS = {
    "ndaq": "http://www.nasdaqtrader.com/"
}


def clean(value):
    """
    Nettoie une valeur provenant du XML Nasdaq.
    """
    if value is None:
        return ""

    return value.strip()


def parse_datetime(date_text, time_text):
    """
    Convertit une date et une heure Nasdaq en datetime.

    Exemples :
        08/10/2026 + 15:50:07.393
        08/10/2026 + 15:50:07
    """

    date_text = clean(date_text)
    time_text = clean(time_text)

    if not date_text or not time_text:
        return None

    # Certains fichiers Nasdaq contiennent des espaces
    # avant la fraction de seconde.
    time_text = time_text.replace(" ", "")

    formats = [
        "%m/%d/%Y %H:%M:%S.%f",
        "%m/%d/%Y %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(
                f"{date_text} {time_text}",
                fmt
            )
        except ValueError:
            continue

    return None


def get_field(item, field):
    """
    Retourne un champ Nasdaq nettoyé.
    """

    return clean(
        item.findtext(
            f"ndaq:{field}",
            default="",
            namespaces=NS
        )
    )


def get_market(item):
    """
    Normalise le champ marché.

    Les XML historiques validés utilisent :
        Mkt

    Le flux live/current validé utilise :
        Market

    Les deux variantes sont normalisées vers :
        market
    """

    market = get_field(
        item,
        "Mkt"
    )

    if market:
        return market

    return get_field(
        item,
        "Market"
    )


def parse_xml_root(root, source_file):
    """
    Parse un arbre XML Nasdaq déjà chargé.

    Retourne une liste d'événements normalisés.
    """

    events = []

    for item in root.findall(".//item"):

        symbol = get_field(
            item,
            "IssueSymbol"
        )

        if not symbol:
            continue

        issue_name = get_field(
            item,
            "IssueName"
        )

        market = get_market(
            item
        )

        reason_code = get_field(
            item,
            "ReasonCode"
        )

        pause_threshold = get_field(
            item,
            "PauseThresholdPrice"
        )

        halt_date = get_field(
            item,
            "HaltDate"
        )

        halt_time = get_field(
            item,
            "HaltTime"
        )

        resumption_date = get_field(
            item,
            "ResumptionDate"
        )

        resumption_quote_time = get_field(
            item,
            "ResumptionQuoteTime"
        )

        resumption_trade_time = get_field(
            item,
            "ResumptionTradeTime"
        )

        halt_start = parse_datetime(
            halt_date,
            halt_time
        )

        # Priorité à ResumptionTradeTime.
        #
        # Le titre est considéré halted jusqu'à la reprise
        # des transactions.

        resumption_time = (
            resumption_trade_time
        )

        if not resumption_time:
            resumption_time = (
                resumption_quote_time
            )

        halt_end = parse_datetime(
            resumption_date,
            resumption_time
        )

        events.append({
            "symbol":
                symbol,

            "issue_name":
                issue_name,

            "market":
                market,

            "reason_code":
                reason_code,

            "halt_date":
                halt_date,

            "halt_time":
                halt_time,

            "resumption_date":
                resumption_date,

            "resumption_quote_time":
                resumption_quote_time,

            "resumption_trade_time":
                resumption_trade_time,

            "pause_threshold_price":
                pause_threshold,

            "halt_start":
                halt_start,

            "halt_end":
                halt_end,

            "source_file":
                source_file,
        })

    return events


def parse_xml_file(xml_file):
    """
    Lit un fichier XML Nasdaq et retourne les événements
    normalisés.

    Compatible avec les variantes historiques et live
    actuellement connues.
    """

    xml_file = Path(
        xml_file
    )

    tree = ET.parse(
        xml_file
    )

    return parse_xml_root(
        tree.getroot(),
        xml_file.name
    )


def parse_xml_bytes(xml_data, source_file):
    """
    Parse directement un document XML Nasdaq reçu en mémoire.
    """

    root = ET.fromstring(
        xml_data
    )

    return parse_xml_root(
        root,
        source_file
    )
